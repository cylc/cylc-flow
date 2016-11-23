#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Provide a class to represent a task proxy in a running suite."""

from collections import namedtuple
from copy import copy
from logging import (
    getLevelName, getLogger, CRITICAL, ERROR, WARNING, INFO, DEBUG)
import os
from pipes import quote
from random import randrange
import re
from shutil import rmtree
import time
import traceback

from isodatetime.timezone import get_local_time_zone

from cylc.mkdir_p import mkdir_p
from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.cycling.iso8601
from cylc.envvar import expandvars
import cylc.flags as flags
from cylc.wallclock import (
    get_current_time_string,
    get_seconds_as_interval_string,
    get_time_string_from_unix_time,
    get_unix_time_from_time_string,
    RE_DATE_TIME_FORMAT_EXTENDED,
)
from cylc.host_select import get_task_host
from cylc.job_file import JobFile
from cylc.job_host import RemoteJobHostManager
from cylc.batch_sys_manager import BATCH_SYS_MANAGER
from cylc.owner import is_remote_user, USER
from cylc.suite_host import is_remote_host, get_suite_host
from parsec.OrderedDict import OrderedDictWithDefaults
from cylc.mp_pool import SuiteProcPool, SuiteProcContext
from cylc.rundb import CylcSuiteDAO
from cylc.task_id import TaskID
from cylc.task_message import TaskMessage
from parsec.util import pdeepcopy, poverride
from parsec.config import ItemNotFoundError
from cylc.task_state import (
    TaskState, TASK_STATUSES_ACTIVE, TASK_STATUS_WAITING,
    TASK_STATUS_READY, TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED, TASK_STATUS_FAILED)
from cylc.task_outputs import (
    TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED)
from cylc.suite_logging import LOG


CustomTaskEventHandlerContext = namedtuple(
    "CustomTaskEventHandlerContext",
    ["key", "ctx_type", "cmd"])


TaskEventMailContext = namedtuple(
    "TaskEventMailContext",
    ["key", "ctx_type", "event", "mail_from", "mail_to", "mail_smtp"])


TaskJobLogsRegisterContext = namedtuple(
    "TaskJobLogsRegisterContext",
    ["key", "ctx_type"])


TaskJobLogsRetrieveContext = namedtuple(
    "TaskJobLogsRetrieveContext",
    ["key", "ctx_type", "user_at_host", "max_size"])


class TaskActionTimer(object):
    """A timer with delays for task actions."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["ctx", "delays", "num", "delay", "timeout", "is_waiting"]

    def __init__(self, ctx=None, delays=None, num=0, delay=None, timeout=None):
        self.ctx = ctx
        if delays:
            self.delays = list(delays)
        else:
            self.delays = [0]
        self.num = num
        self.delay = delay
        self.timeout = timeout
        self.is_waiting = False

    def delay_as_seconds(self):
        """Return the delay as PTnS, where n is number of seconds."""
        return get_seconds_as_interval_string(self.delay)

    def is_delay_done(self, now=None):
        """Is timeout done?"""
        if self.timeout is None:
            return False
        if now is None:
            now = time.time()
        return now > self.timeout

    def is_timeout_set(self):
        """Return True if timeout is set."""
        return self.timeout is not None

    def next(self, no_exhaust=False):
        """Return the next retry delay.

        When delay list has no more item:
        * Return None if no_exhaust is False
        * Return the final delay if no_exhaust is True.
        """
        try:
            self.delay = self.delays[self.num]
        except IndexError:
            if not no_exhaust:
                self.delay = None
        if self.delay is not None:
            self.timeout = time.time() + self.delay
            self.num += 1
        return self.delay

    def set_waiting(self):
        """Set waiting flag, while waiting for action to complete."""
        self.delay = None
        self.is_waiting = True
        self.timeout = None

    def unset_waiting(self):
        """Unset waiting flag after an action has completed."""
        self.is_waiting = False

    def timeout_as_str(self):
        """Return the timeout as an ISO8601 date-time string."""
        return get_time_string_from_unix_time(self.timeout)


class TaskProxySequenceBoundsError(ValueError):
    """Error on TaskProxy.__init__ with out of sequence bounds start point."""

    def __str__(self):
        return "Not loading %s (out of sequence bounds)" % self.args[0]


class TaskProxy(object):
    """The task proxy."""

    # RETRY LOGIC:
    #  1) ABSOLUTE SUBMIT NUMBER increments every time a task is
    #  submitted, manually or automatically by (submission or execution)
    # retries; whether or not the task actually begins executing, and is
    # appended to the task log root filename.
    #  2) SUBMISSION TRY NUMBER increments when task job submission
    # fails, if submission retries are configured, but resets to 1 if
    # the task begins executing; and is used for accounting purposes.
    #  3) EXECUTION TRY NUMBER increments only when task execution fails,
    # if execution retries are configured; and is passed to task
    # environments to allow changed behaviour after previous failures.

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["JOB_LOG_FMT_1", "JOB_LOG_FMT_M", "CUSTOM_EVENT_HANDLER",
                 "EVENT_MAIL", "HEAD_MODE_LOCAL", "HEAD_MODE_REMOTE",
                 "JOB_FILE_BASE", "JOB_KILL", "JOB_LOGS_RETRIEVE", "JOB_POLL",
                 "JOB_SUBMIT", "MANAGE_JOB_LOGS_TRY_DELAYS", "NN",
                 "LOGGING_LVL_OF", "RE_MESSAGE_TIME", "TABLE_TASK_JOBS",
                 "TABLE_TASK_EVENTS", "TABLE_TASK_STATES", "POLLED_INDICATOR",
                 "event_handler_env", "stop_sim_mode_job_submission", "tdef",
                 "submit_num", "validate_mode", "message_queue", "point",
                 "cleanup_cutoff", "identity", "has_spawned",
                 "point_as_seconds", "stop_point", "manual_trigger",
                 "is_manual_submit", "summary", "local_job_file_path",
                 "retries_configured", "run_try_state", "sub_try_state",
                 "event_handler_try_states",
                 "execution_time_limit_poll_timer", "db_inserts_map",
                 "db_updates_map", "suite_name", "task_host", "task_owner",
                 "user_at_host", "job_vacated", "poll_timers",
                 "event_hooks", "sim_mode_run_length",
                 "delayed_start_str", "delayed_start", "expire_time_str",
                 "expire_time", "state"]

    # Format string for single line output
    JOB_LOG_FMT_1 = "%(timestamp)s [%(cmd_key)s %(attr)s] %(mesg)s"
    # Format string for multi-line output
    JOB_LOG_FMT_M = "%(timestamp)s [%(cmd_key)s %(attr)s]\n\n%(mesg)s\n"

    CUSTOM_EVENT_HANDLER = "event-handler"
    EVENT_MAIL = "event-mail"
    HEAD_MODE_LOCAL = "local"
    HEAD_MODE_REMOTE = "remote"
    JOB_FILE_BASE = BATCH_SYS_MANAGER.JOB_FILE_BASE
    JOB_KILL = "job-kill"
    JOB_LOGS_RETRIEVE = "job-logs-retrieve"
    JOB_POLL = "job-poll"
    JOB_SUBMIT = "job-submit"
    MANAGE_JOB_LOGS_TRY_DELAYS = (0, 30, 180)  # PT0S, PT30S, PT3M
    NN = "NN"

    LOGGING_LVL_OF = {
        "INFO": INFO,
        "NORMAL": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
        "DEBUG": DEBUG,
    }
    RE_MESSAGE_TIME = re.compile(
        '\A(.+) at (' + RE_DATE_TIME_FORMAT_EXTENDED + ')\Z')

    TABLE_TASK_JOBS = CylcSuiteDAO.TABLE_TASK_JOBS
    TABLE_TASK_EVENTS = CylcSuiteDAO.TABLE_TASK_EVENTS
    TABLE_TASK_STATES = CylcSuiteDAO.TABLE_TASK_STATES

    POLLED_INDICATOR = "(polled)"

    event_handler_env = {}
    stop_sim_mode_job_submission = False

    def __init__(
            self, tdef, start_point, status=TASK_STATUS_WAITING,
            has_spawned=False, stop_point=None, is_startup=False,
            validate_mode=False, submit_num=0, is_reload_or_restart=False,
            pre_reload_inst=None, message_queue=None):
        self.tdef = tdef
        if submit_num is None:
            self.submit_num = 0
        else:
            self.submit_num = submit_num
        self.validate_mode = validate_mode
        self.message_queue = message_queue

        if is_startup:
            # adjust up to the first on-sequence cycle point
            adjusted = []
            for seq in self.tdef.sequences:
                adj = seq.get_first_point(start_point)
                if adj:
                    # may be None if out of sequence bounds
                    adjusted.append(adj)
            if not adjusted:
                # This task is out of sequence bounds
                raise TaskProxySequenceBoundsError(self.tdef.name)
            self.point = min(adjusted)
            self.cleanup_cutoff = self.tdef.get_cleanup_cutoff_point(
                self.point, self.tdef.intercycle_offsets)
            self.identity = TaskID.get(self.tdef.name, self.point)
        else:
            self.point = start_point
            self.cleanup_cutoff = self.tdef.get_cleanup_cutoff_point(
                self.point, self.tdef.intercycle_offsets)
            self.identity = TaskID.get(self.tdef.name, self.point)

        self.has_spawned = has_spawned

        self.point_as_seconds = None

        # Manually inserted tasks may have a final cycle point set.
        self.stop_point = stop_point

        self.manual_trigger = False
        self.is_manual_submit = False

        self.summary = {
            'latest_message': "",
            'submitted_time': None,
            'submitted_time_string': None,
            'submit_num': self.submit_num,
            'started_time': None,
            'started_time_string': None,
            'finished_time': None,
            'finished_time_string': None,
            'name': self.tdef.name,
            'description': self.tdef.rtconfig['description'],
            'title': self.tdef.rtconfig['title'],
            'label': str(self.point),
            'logfiles': [],
            'job_hosts': {},
            'execution_time_limit': None,
        }
        for lfile in self.tdef.rtconfig['extra log files']:
            self.summary['logfiles'].append(expandvars(lfile))

        self.local_job_file_path = None

        self.retries_configured = False

        self.run_try_state = TaskActionTimer()
        self.sub_try_state = TaskActionTimer()
        self.event_handler_try_states = {}
        self.execution_time_limit_poll_timer = None

        self.db_inserts_map = {
            self.TABLE_TASK_JOBS: [],
            self.TABLE_TASK_STATES: [],
            self.TABLE_TASK_EVENTS: [],
        }
        self.db_updates_map = {
            self.TABLE_TASK_JOBS: [],
            self.TABLE_TASK_STATES: [],
        }

        # TODO - should take suite name from config!
        self.suite_name = os.environ['CYLC_SUITE_NAME']

        # In case task owner and host are needed by db_events_insert()
        # for pre-submission events, set their initial values as if
        # local (we can't know the correct host prior to this because
        # dynamic host selection could be used).
        self.task_host = 'localhost'
        self.task_owner = None
        self.user_at_host = self.task_host

        self.job_vacated = False

        self.poll_timers = {"submission": None, "execution": None}

        # An initial db state entry is created at task proxy init. On reloading
        # or restarting the suite, the task proxies already have this db entry.
        if (not self.validate_mode and not is_reload_or_restart and
                self.submit_num == 0):
            self.db_inserts_map[self.TABLE_TASK_STATES].append({
                "time_created": get_current_time_string(),
                "time_updated": get_current_time_string(),
                "status": status})

        if not self.validate_mode and self.submit_num > 0:
            self.db_updates_map[self.TABLE_TASK_STATES].append({
                "time_updated": get_current_time_string(),
                "status": status})

        self.event_hooks = None
        self.sim_mode_run_length = None
        self.set_from_rtconfig()
        self.delayed_start_str = None
        self.delayed_start = None
        self.expire_time_str = None
        self.expire_time = None

        self.state = TaskState(status, self.point, self.identity, tdef,
                               self.db_events_insert, self.db_update_status,
                               self.log)

        if tdef.sequential:
            # Adjust clean-up cutoff.
            p_next = None
            adjusted = []
            for seq in tdef.sequences:
                nxt = seq.get_next_point(self.point)
                if nxt:
                    # may be None if beyond the sequence bounds
                    adjusted.append(nxt)
            if adjusted:
                p_next = min(adjusted)
                if (self.cleanup_cutoff is not None and
                        self.cleanup_cutoff < p_next):
                    self.cleanup_cutoff = p_next

        if is_reload_or_restart and pre_reload_inst is not None:
            self.log(INFO, 'reloaded task definition')
            if pre_reload_inst.state.status in TASK_STATUSES_ACTIVE:
                self.log(WARNING, "job is active with pre-reload settings")
            # Retain some state from my pre suite-reload predecessor.
            self.has_spawned = pre_reload_inst.has_spawned
            self.summary = pre_reload_inst.summary
            self.run_try_state = pre_reload_inst.run_try_state
            self.sub_try_state = pre_reload_inst.sub_try_state
            self.submit_num = pre_reload_inst.submit_num
            self.db_inserts_map = pre_reload_inst.db_inserts_map
            self.db_updates_map = pre_reload_inst.db_updates_map
            # Retain status of outputs.
            for msg, oid in pre_reload_inst.state.outputs.completed.items():
                self.state.outputs.completed[msg] = oid
                try:
                    del self.state.outputs.not_completed[msg]
                except KeyError:
                    pass

    def _get_events_conf(self, key, default=None):
        """Return an events setting from suite then global configuration."""
        for getter in [self.event_hooks, GLOBAL_CFG.get()["task events"]]:
            try:
                value = getter.get(key)
                if value is not None:
                    return value
            except (ItemNotFoundError, KeyError):
                pass
        return default

    def _get_host_conf(self, key, default=None, skey="remote"):
        """Return a host setting from suite then global configuration."""
        if self.tdef.rtconfig[skey].get(key) is not None:
            return self.tdef.rtconfig[skey][key]
        else:
            try:
                return GLOBAL_CFG.get_host_item(
                    key, self.task_host, self.task_owner)
            except (KeyError, ItemNotFoundError):
                pass
        return default

    def log(self, lvl=INFO, msg=""):
        """Log a message of this task proxy."""
        msg = "[%s] -%s" % (self.identity, msg)
        LOG.log(lvl, msg)

    def command_log(self, ctx):
        """Log an activity for a job of this task proxy."""
        ctx_str = str(ctx)
        if not ctx_str:
            return
        submit_num = self.NN
        if isinstance(ctx.cmd_key, tuple):  # An event handler
            submit_num = ctx.cmd_key[-1]
        job_activity_log = self.get_job_log_path(
            self.HEAD_MODE_LOCAL, submit_num, "job-activity.log")
        try:
            with open(job_activity_log, "ab") as handle:
                handle.write(ctx_str + '\n')
        except IOError as exc:
            LOG.warning(
                "%s: write failed\n%s" % (job_activity_log, exc))
        if ctx.cmd and ctx.ret_code:
            LOG.error(ctx_str)
        elif ctx.cmd:
            LOG.debug(ctx_str)

    def db_events_insert(self, event="", message=""):
        """Record an event to the DB."""
        self.db_inserts_map[self.TABLE_TASK_EVENTS].append({
            "time": get_current_time_string(),
            "event": event,
            "message": message})

    def db_update_status(self):
        """Update suite runtime DB task states table."""
        self.db_updates_map[self.TABLE_TASK_STATES].append({
            "time_updated": get_current_time_string(),
            "submit_num": self.submit_num,
            "try_num": self.run_try_state.num + 1,
            "status": self.state.status})

    def retry_delay_done(self):
        """Is retry delay done? Can I retry now?"""
        now = time.time()
        return (self.run_try_state.is_delay_done(now) or
                self.sub_try_state.is_delay_done(now))

    def ready_to_run(self):
        """Am I in a pre-run state but ready to run?

        Queued tasks are not counted as they've already been deemed ready.

        """
        ready = self.state.is_ready_to_run(self.retry_delay_done(),
                                           self.start_time_reached())
        if ready and self._has_expired():
            self.log(WARNING, 'Task expired (skipping job).')
            self.setup_event_handlers(
                "expired", 'Task expired (skipping job).')
            self.state.set_expired()
            return False
        return ready

    def get_point_as_seconds(self):
        """Compute and store my cycle point as seconds."""
        if self.point_as_seconds is None:
            iso_timepoint = cylc.cycling.iso8601.point_parse(str(self.point))
            self.point_as_seconds = int(iso_timepoint.get(
                "seconds_since_unix_epoch"))
            if iso_timepoint.time_zone.unknown:
                utc_offset_hours, utc_offset_minutes = (
                    get_local_time_zone())
                utc_offset_in_seconds = (
                    3600 * utc_offset_hours + 60 * utc_offset_minutes)
                self.point_as_seconds += utc_offset_in_seconds
        return self.point_as_seconds

    @staticmethod
    def get_offset_as_seconds(offset):
        """Return an ISO interval as seconds."""
        iso_offset = cylc.cycling.iso8601.interval_parse(str(offset))
        return int(iso_offset.get_seconds())

    def start_time_reached(self):
        """Has this task reached its clock trigger time?"""
        if self.tdef.clocktrigger_offset is None:
            return True
        if self.delayed_start is None:
            self.delayed_start = (
                self.get_point_as_seconds() +
                self.get_offset_as_seconds(self.tdef.clocktrigger_offset))
            self.delayed_start_str = get_time_string_from_unix_time(
                self.delayed_start)
        return time.time() > self.delayed_start

    def _has_expired(self):
        """Is this task past its use-by date?"""
        if self.tdef.expiration_offset is None:
            return False
        if self.expire_time is None:
            self.expire_time = (
                self.get_point_as_seconds() +
                self.get_offset_as_seconds(self.tdef.expiration_offset))
            self.expire_time_str = get_time_string_from_unix_time(
                self.expire_time)
        return time.time() > self.expire_time

    def job_submission_callback(self, result):
        """Callback on job submission."""
        if result.out is not None:
            out = ""
            for line in result.out.splitlines(True):
                if line.startswith(
                        BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID + "="):
                    self.summary['submit_method_id'] = line.strip().replace(
                        BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID + "=", "")
                else:
                    out += line
            result.out = out
        self.command_log(result)

        if result.ret_code == SuiteProcPool.JOB_SKIPPED_FLAG:
            return

        if self.summary['submit_method_id'] and result.ret_code == 0:
            self.job_submission_succeeded()
        else:
            self.job_submission_failed()

    def job_poll_callback(self, cmd_ctx, line):
        """Callback on job poll."""
        ctx = SuiteProcContext(self.JOB_POLL, None)
        ctx.out = line
        ctx.ret_code = 0

        items = line.split("|")
        # See cylc.batch_sys_manager.JobPollContext
        try:
            (
                batch_sys_exit_polled, run_status, run_signal,
                time_submit_exit, time_run, time_run_exit
            ) = items[4:10]
        except IndexError:
            self.summary['latest_message'] = 'poll failed'
            flags.iflag = True
            ctx.cmd = cmd_ctx.cmd  # print original command on failure
            return
        finally:
            self.command_log(ctx)
        if run_status == "1" and run_signal in ["ERR", "EXIT"]:
            # Failed normally
            self.process_incoming_message(
                INFO, TASK_OUTPUT_FAILED, time_run_exit)
        elif run_status == "1" and batch_sys_exit_polled == "1":
            # Failed by a signal, and no longer in batch system
            self.process_incoming_message(
                INFO, TASK_OUTPUT_FAILED, time_run_exit)
            self.process_incoming_message(
                INFO, TaskMessage.FAIL_MESSAGE_PREFIX + run_signal,
                time_run_exit)
        elif run_status == "1":
            # The job has terminated, but is still managed by batch system.
            # Some batch system may restart a job in this state, so don't
            # mark as failed yet.
            self.process_incoming_message(INFO, TASK_OUTPUT_STARTED, time_run)
        elif run_status == "0":
            # The job succeeded
            self.process_incoming_message(
                INFO, TASK_OUTPUT_SUCCEEDED, time_run_exit)
        elif time_run and batch_sys_exit_polled == "1":
            # The job has terminated without executing the error trap
            self.process_incoming_message(
                INFO, TASK_OUTPUT_FAILED, "")
        elif time_run:
            # The job has started, and is still managed by batch system
            self.process_incoming_message(INFO, TASK_OUTPUT_STARTED, time_run)
        elif batch_sys_exit_polled == "1":
            # The job never ran, and no longer in batch system
            self.process_incoming_message(
                INFO, "submission failed", time_submit_exit)
        else:
            # The job never ran, and is in batch system
            self.process_incoming_message(
                INFO, TASK_STATUS_SUBMITTED, time_submit_exit)

    def job_poll_message_callback(self, cmd_ctx, line):
        """Callback on job poll message."""
        ctx = SuiteProcContext(self.JOB_POLL, None)
        ctx.out = line
        try:
            event_time, priority, message = line.split("|")[2:5]
        except ValueError:
            ctx.ret_code = 1
            ctx.cmd = cmd_ctx.cmd  # print original command on failure
        else:
            ctx.ret_code = 0
            self.process_incoming_message(priority, message, event_time)
        self.command_log(ctx)

    def job_kill_callback(self, cmd_ctx, line):
        """Callback on job kill."""
        ctx = SuiteProcContext(self.JOB_KILL, None)
        ctx.out = line
        try:
            ctx.timestamp, _, ctx.ret_code = line.split("|", 2)
        except ValueError:
            ctx.ret_code = 1
            ctx.cmd = cmd_ctx.cmd  # print original command on failure
        else:
            ctx.ret_code = int(ctx.ret_code)
            if ctx.ret_code:
                ctx.cmd = cmd_ctx.cmd  # print original command on failure
        self.command_log(ctx)
        log_lvl = INFO
        log_msg = 'killed'
        if ctx.ret_code:  # non-zero exit status
            log_lvl = WARNING
            log_msg = 'kill failed'
            self.state.kill_failed = True
        elif self.state.status == TASK_STATUS_SUBMITTED:
            self.job_submission_failed()
            flags.iflag = True
        elif self.state.status == TASK_STATUS_RUNNING:
            self.job_execution_failed()
            flags.iflag = True
        else:
            log_lvl = WARNING
            log_msg = (
                'ignoring job kill result, unexpected task state: %s' %
                self.state.status)
        self.summary['latest_message'] = log_msg
        self.log(log_lvl, "job(%02d) %s" % (self.submit_num, log_msg))

    def job_submit_callback(self, cmd_ctx, line):
        """Callback on job submit."""
        ctx = SuiteProcContext(self.JOB_SUBMIT, None)
        ctx.out = line
        items = line.split("|")
        try:
            ctx.timestamp, _, ctx.ret_code = items[0:3]
        except ValueError:
            ctx.ret_code = 1
            ctx.cmd = cmd_ctx.cmd  # print original command on failure
        else:
            ctx.ret_code = int(ctx.ret_code)
            if ctx.ret_code:
                ctx.cmd = cmd_ctx.cmd  # print original command on failure
        self.command_log(ctx)

        if ctx.ret_code == SuiteProcPool.JOB_SKIPPED_FLAG:
            return

        try:
            self.summary['submit_method_id'] = items[3]
        except IndexError:
            self.summary['submit_method_id'] = None
        if self.summary['submit_method_id'] and ctx.ret_code == 0:
            self.job_submission_succeeded()
        else:
            self.job_submission_failed()

    def job_cmd_out_callback(self, cmd_ctx, line):
        """Callback on job command STDOUT/STDERR."""
        job_activity_log = self.get_job_log_path(
            self.HEAD_MODE_LOCAL, self.NN, "job-activity.log")
        if cmd_ctx.cmd_kwargs.get("host") and cmd_ctx.cmd_kwargs.get("user"):
            user_at_host = "(%(user)s@%(host)s) " % cmd_ctx.cmd_kwargs
        elif cmd_ctx.cmd_kwargs.get("host"):
            user_at_host = "(%(host)s) " % cmd_ctx.cmd_kwargs
        elif cmd_ctx.cmd_kwargs.get("user"):
            user_at_host = "(%(user)s@localhost) " % cmd_ctx.cmd_kwargs
        else:
            user_at_host = ""
        try:
            timestamp, _, content = line.split("|")
        except ValueError:
            pass
        else:
            line = "%s %s" % (timestamp, content)
        try:
            with open(job_activity_log, "ab") as handle:
                if not line.endswith("\n"):
                    line += "\n"
                handle.write(user_at_host + line)
        except IOError as exc:
            self.log(WARNING, "%s: write failed\n%s" % (job_activity_log, exc))

    def setup_event_handlers(
            self, event, message, db_update=True, db_event=None, db_msg=None):
        """Set up event handlers."""
        # extra args for inconsistent use between events, logging, and db
        # updates
        db_event = db_event or event
        if db_update:
            self.db_events_insert(event=db_event, message=db_msg)

        if self.tdef.run_mode != 'live':
            return

        self.setup_job_logs_retrieval(event, message)
        self.setup_event_mail(event, message)
        self.setup_custom_event_handlers(event, message)

    def setup_job_logs_retrieval(self, event, _=None):
        """Set up remote job logs retrieval."""
        # TODO - use string constants for event names.
        key2 = (self.JOB_LOGS_RETRIEVE, self.submit_num)
        if (event not in ['failed', 'retry', 'succeeded'] or
                self.user_at_host in [USER + '@localhost', 'localhost'] or
                not self._get_host_conf("retrieve job logs") or
                key2 in self.event_handler_try_states):
            return
        self.event_handler_try_states[key2] = TaskActionTimer(
            TaskJobLogsRetrieveContext(
                # key
                self.JOB_LOGS_RETRIEVE,
                # ctx_type
                self.JOB_LOGS_RETRIEVE,
                self.user_at_host,
                # max_size
                self._get_host_conf("retrieve job logs max size"),
            ),
            self._get_host_conf("retrieve job logs retry delays", []))

    def setup_event_mail(self, event, _):
        """Event notification, by email."""
        key1 = (self.EVENT_MAIL, event)
        if ((key1, self.submit_num) in self.event_handler_try_states or
                event not in self._get_events_conf("mail events", [])):
            return

        self.event_handler_try_states[(key1, self.submit_num)] = (
            TaskActionTimer(
                TaskEventMailContext(
                    key1,
                    self.EVENT_MAIL,  # ctx_type
                    event,
                    self._get_events_conf(  # mail_from
                        "mail from",
                        "notifications@" + get_suite_host(),
                    ),
                    self._get_events_conf("mail to", USER),  # mail_to
                    self._get_events_conf("mail smtp"),  # mail_smtp
                ),
                self._get_events_conf("mail retry delays", [])))

    def setup_custom_event_handlers(self, event, message, only_list=None):
        """Call custom event handlers."""
        handlers = []
        if self.event_hooks[event + ' handler']:
            handlers = self.event_hooks[event + ' handler']
        elif (self._get_events_conf('handlers', []) and
                event in self._get_events_conf('handler events', [])):
            handlers = self._get_events_conf('handlers', [])
        retry_delays = self._get_events_conf(
            'handler retry delays',
            self._get_host_conf("task event handler retry delays", []))
        for i, handler in enumerate(handlers):
            key1 = ("%s-%02d" % (self.CUSTOM_EVENT_HANDLER, i), event)
            if (key1, self.submit_num) in self.event_handler_try_states or (
                    only_list and i not in only_list):
                continue
            cmd = handler % {
                "event": quote(event),
                "suite": quote(self.suite_name),
                "point": quote(str(self.point)),
                "name": quote(self.tdef.name),
                "submit_num": self.submit_num,
                "id": quote(self.identity),
                "message": quote(message),
            }
            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = "%s '%s' '%s' '%s' '%s'" % (
                    handler, event, self.suite_name, self.identity, message)
            self.log(DEBUG, "Queueing %s handler: %s" % (event, cmd))
            self.event_handler_try_states[(key1, self.submit_num)] = (
                TaskActionTimer(
                    CustomTaskEventHandlerContext(
                        key1,
                        self.CUSTOM_EVENT_HANDLER,
                        cmd,
                    ),
                    retry_delays))

    def custom_event_handler_callback(self, result):
        """Callback when a custom event handler is done."""
        self.command_log(result)
        try:
            if result.ret_code == 0:
                del self.event_handler_try_states[result.cmd_key]
            else:
                self.event_handler_try_states[result.cmd_key].unset_waiting()
        except KeyError:
            pass

    def job_submission_failed(self, event_time=None):
        """Handle job submission failure."""
        self.log(ERROR, 'submission failed')
        if event_time is None:
            event_time = get_current_time_string()
        self.db_updates_map[self.TABLE_TASK_JOBS].append({
            "time_submit_exit": get_current_time_string(),
            "submit_status": 1,
        })
        try:
            del self.summary['submit_method_id']
        except KeyError:
            pass
        if self.sub_try_state.next() is None:
            # No submission retry lined up: definitive failure.
            self.summary['finished_time'] = float(
                get_unix_time_from_time_string(event_time))
            self.summary['finished_time_string'] = event_time
            flags.pflag = True
            # See github #476.
            self.setup_event_handlers(
                'submission failed', 'job submission failed')
            self.state.set_submit_failed()
        else:
            # There is a submission retry lined up.
            timeout_str = self.sub_try_state.timeout_as_str()

            delay_msg = "submit-retrying in %s" % (
                self.sub_try_state.delay_as_seconds())
            msg = "submission failed, %s (after %s)" % (delay_msg, timeout_str)
            self.log(INFO, "job(%02d) " % self.submit_num + msg)
            self.summary['latest_message'] = msg
            self.db_events_insert(
                event="submission failed", message=delay_msg)
            # TODO - is this insert redundant with setup_event_handlers?
            self.db_events_insert(
                event="submission failed",
                message="submit-retrying in " + str(self.sub_try_state.delay))
            self.setup_event_handlers(
                "submission retry", "job submission failed, " + delay_msg)
            self.state.set_submit_retry()

    def job_submission_succeeded(self):
        """Handle job submission succeeded."""
        if self.summary.get('submit_method_id') is not None:
            self.log(
                INFO, 'submit_method_id=' + self.summary['submit_method_id'])
        self.log(INFO, 'submission succeeded')
        now = time.time()
        now_string = get_time_string_from_unix_time(now)
        self.db_updates_map[self.TABLE_TASK_JOBS].append({
            "time_submit_exit": now,
            "submit_status": 0,
            "batch_sys_job_id": self.summary.get('submit_method_id')})

        if self.tdef.run_mode == 'simulation':
            # Simulate job execution at this point.
            if self.__class__.stop_sim_mode_job_submission:
                self.state.set_ready_to_submit()
            else:
                self.summary['started_time'] = now
                self.summary['started_time_string'] = now_string
                self.state.set_executing()
            return

        self.summary['started_time'] = None
        self.summary['started_time_string'] = None
        self.summary['finished_time'] = None
        self.summary['finished_time_string'] = None

        self.summary['submitted_time'] = now
        self.summary['submitted_time_string'] = now_string
        self.summary['latest_message'] = TASK_STATUS_SUBMITTED
        self.setup_event_handlers("submitted", 'job submitted',
                                  db_event='submission succeeded')

        if self.state.set_submit_succeeded():
            submit_timeout = self._get_events_conf('submission timeout')
            if submit_timeout:
                self.state.submission_timer_timeout = (
                    self.summary['submitted_time'] + submit_timeout)
            else:
                self.state.submission_timer_timeout = None
            self._set_next_poll_time('submission')

    def job_execution_failed(self, event_time=None):
        """Handle a job failure."""
        if event_time is None:
            self.summary['finished_time'] = time.time()
            self.summary['finished_time_string'] = (
                get_time_string_from_unix_time(self.summary['finished_time']))
        else:
            self.summary['finished_time'] = float(
                get_unix_time_from_time_string(event_time))
            self.summary['finished_time_string'] = event_time
        self.db_updates_map[self.TABLE_TASK_JOBS].append({
            "run_status": 1,
            "time_run_exit": self.summary['finished_time_string'],
        })
        self.state.execution_timer_timeout = None
        if self.run_try_state.next() is None:
            # No retry lined up: definitive failure.
            # Note the TASK_STATUS_FAILED output is only added if needed.
            flags.pflag = True
            self.state.set_execution_failed()
            self.setup_event_handlers("failed", 'job failed')
        else:
            # There is a retry lined up
            timeout_str = self.run_try_state.timeout_as_str()
            delay_msg = "retrying in %s" % (
                self.run_try_state.delay_as_seconds())
            msg = "failed, %s (after %s)" % (delay_msg, timeout_str)
            self.log(INFO, "job(%02d) " % self.submit_num + msg)
            self.summary['latest_message'] = msg
            self.setup_event_handlers(
                "retry", "job failed, " + delay_msg, db_msg=delay_msg)
            self.state.set_execution_retry()

    def reset_manual_trigger(self):
        """This is called immediately after manual trigger flag used."""
        if self.manual_trigger:
            self.manual_trigger = False
            self.is_manual_submit = True
            # unset any retry delay timers
            self.run_try_state.timeout = None
            self.sub_try_state.timeout = None

    def set_from_rtconfig(self, cfg=None):
        """Populate task proxy with runtime configuration.

        Some [runtime] config requiring consistency checking on reload,
        and self variables requiring updating for the same.

        """

        if cfg:
            rtconfig = cfg
        else:
            rtconfig = self.tdef.rtconfig

        if not self.retries_configured:
            # configure retry delays before the first try
            self.retries_configured = True
            # TODO - saving the retry delay lists here is not necessary
            # (it can be handled like the polling interval lists).
            if (self.tdef.run_mode == 'live' or
                    (self.tdef.run_mode == 'simulation' and
                        not rtconfig['simulation mode']['disable retries']) or
                    (self.tdef.run_mode == 'dummy' and
                        not rtconfig['dummy mode']['disable retries'])):
                # note that a *copy* of the retry delays list is needed
                # so that all instances of the same task don't pop off
                # the same deque (but copy of rtconfig above solves this).
                self.run_try_state.delays = list(
                    rtconfig['job']['execution retry delays'])
                self.sub_try_state.delays = list(
                    rtconfig['job']['submission retry delays'])

        rrange = rtconfig['simulation mode']['run time range']
        if len(rrange) != 2:
            raise Exception("ERROR, " + self.tdef.name + ": simulation mode " +
                            "run time range should be ISO 8601-compatible")
        try:
            self.sim_mode_run_length = randrange(rrange[0], rrange[1])
        except Exception, exc:
            traceback.print_exc(exc)
            raise Exception(
                "ERROR: simulation mode task run time range must be [MIN,MAX)")

        self.event_hooks = rtconfig['events']

        for key in 'submission', 'execution':
            values = self._get_host_conf(
                key + ' polling intervals', skey='job')
            if values:
                self.poll_timers[key] = TaskActionTimer(delays=values)

    def submit(self):
        """For "cylc submit". See also "TaskPool.submit_task_jobs"."""

        self.state.set_ready_to_submit()

        # Reset flag so any re-triggering will generate a new job file.
        self.local_job_file_path = None

        cmd_key = self.JOB_SUBMIT
        args = [self.get_job_log_path(
            self.HEAD_MODE_REMOTE, tail=self.JOB_FILE_BASE)]
        stdin_file_paths = [self.get_job_log_path(
            self.HEAD_MODE_LOCAL, tail=self.JOB_FILE_BASE)]

        cmd = ["cylc", cmd_key]
        if cylc.flags.debug:
            cmd.append("--debug")
        remote_mode = False
        for key, value, test_func in [
                ('host', self.task_host, is_remote_host),
                ('user', self.task_owner, is_remote_user)]:
            if test_func(value):
                cmd.append('--%s=%s' % (key, value))
                remote_mode = True
        if remote_mode:
            cmd.append('--remote-mode')
        cmd.append("--")
        cmd += list(args)

        self.log(INFO, "job(%02d) initiate %s" % (self.submit_num, cmd_key))
        ctx = SuiteProcContext(
            cmd_key, cmd, stdin_file_paths=stdin_file_paths)
        return SuiteProcPool.get_inst().put_command(
            ctx, self.job_submission_callback)

    def prep_submit(self, dry_run=False, overrides=None):
        """Prepare job submission.

        Return self on a good preparation.

        """
        if self.tdef.run_mode == 'simulation' or (
                self.local_job_file_path and not dry_run):
            return self

        try:
            job_conf = self._prep_submit_impl(overrides)
            local_job_file_path = self.get_job_log_path(
                self.HEAD_MODE_LOCAL, tail=self.JOB_FILE_BASE)
            JobFile.get_inst().write(local_job_file_path, job_conf)
        except Exception, exc:
            # Could be a bad command template.
            if flags.debug:
                traceback.print_exc()
            self.command_log(SuiteProcContext(
                self.JOB_SUBMIT, '(prepare job file)', err=exc,
                ret_code=1))
            self.job_submission_failed()
            return
        self.local_job_file_path = local_job_file_path

        if dry_run:
            # This will be shown next to submit num in gcylc:
            self.summary['latest_message'] = 'job file written for edit-run'
            self.log(WARNING, self.summary['latest_message'])

        # Return value used by "cylc submit" and "cylc jobscript":
        return self

    def _prep_submit_impl(self, overrides=None):
        """Helper for self.prep_submit."""
        self.log(DEBUG, "incrementing submit number")
        self.submit_num += 1
        self.summary['submit_num'] = self.submit_num
        self.local_job_file_path = None
        self.db_events_insert(event="incrementing submit number")
        self.db_inserts_map[self.TABLE_TASK_JOBS].append({
            "is_manual_submit": self.is_manual_submit,
            "try_num": self.run_try_state.num + 1,
            "time_submit": get_current_time_string(),
        })
        if overrides:
            rtconfig = pdeepcopy(self.tdef.rtconfig)
            poverride(rtconfig, overrides)
        else:
            rtconfig = self.tdef.rtconfig

        self.set_from_rtconfig(rtconfig)

        # construct the job_sub_method here so that a new one is used if
        # the task is re-triggered by the suite operator - so it will
        # get new stdout/stderr logfiles and not overwrite the old ones.

        # dynamic instantiation - don't know job sub method till run time.
        self.summary['batch_sys_name'] = rtconfig['job']['batch system']
        self.summary['execution_time_limit'] = (
            rtconfig['job']['execution time limit'])

        # Determine task host settings now, just before job submission,
        # because dynamic host selection may be used.

        # host may be None (= run task on suite host)
        self.task_host = get_task_host(rtconfig['remote']['host'])
        if not self.task_host:
            self.task_host = 'localhost'
        elif self.task_host != "localhost":
            self.log(INFO, "Task host: " + self.task_host)

        self.task_owner = rtconfig['remote']['owner']

        if self.task_owner:
            self.user_at_host = self.task_owner + "@" + self.task_host
        else:
            self.user_at_host = self.task_host
        self.summary['host'] = self.user_at_host
        self.summary['job_hosts'][self.submit_num] = self.user_at_host
        try:
            batch_sys_conf = self._get_host_conf('batch systems')[
                rtconfig['job']['batch system']]
        except (TypeError, KeyError):
            batch_sys_conf = OrderedDictWithDefaults()
        if self.summary['execution_time_limit']:
            # Default = 1, 2 and 7 minutes intervals, roughly 1, 3 and 10
            # minutes after time limit exceeded
            self.execution_time_limit_poll_timer = (
                TaskActionTimer(delays=batch_sys_conf.get(
                    'execution time limit polling intervals', [60, 120, 420])))

        RemoteJobHostManager.get_inst().init_suite_run_dir(
            self.suite_name, self.user_at_host)
        self.db_updates_map[self.TABLE_TASK_JOBS].append({
            "user_at_host": self.user_at_host,
            "batch_sys_name": self.summary['batch_sys_name'],
        })
        self.is_manual_submit = False

        script, pre_script, post_script = self._get_job_scripts(rtconfig)
        execution_time_limit = rtconfig['job']['execution time limit']
        if execution_time_limit:
            execution_time_limit = float(execution_time_limit)

        # Location of job file, etc
        self._create_job_log_path()

        return {
            'batch system name': rtconfig['job']['batch system'],
            'batch submit command template': (
                rtconfig['job']['batch submit command template']),
            'batch system conf': batch_sys_conf,
            'directives': rtconfig['directives'],
            'execution time limit': execution_time_limit,
            'env-script': rtconfig['env-script'],
            'host': self.task_host,
            'init-script': rtconfig['init-script'],
            'job file path': self.get_job_log_path(
                self.HEAD_MODE_REMOTE, tail=self.JOB_FILE_BASE),
            'job log dir': self.get_job_log_path(),
            'job script shell': rtconfig['job']['shell'],
            'local job file path': self.get_job_log_path(
                self.HEAD_MODE_LOCAL, tail=self.JOB_FILE_BASE),
            'namespace hierarchy': self.tdef.namespace_hierarchy,
            'owner': self.task_owner,
            'post-script': post_script,
            'pre-script': pre_script,
            'remote suite path': (
                rtconfig['remote']['suite definition directory']),
            'runtime environment': rtconfig['environment'],
            'script': script,
            'submit num': self.submit_num,
            'suite name': self.suite_name,
            'task id': self.identity,
            'try number': self.run_try_state.num + 1,
            'work sub-directory': rtconfig['work sub-directory'],
        }

    def _get_job_scripts(self, rtconfig):
        """Return script, pre-script, post-script for a job."""
        script = rtconfig['script']
        pre_script = rtconfig['pre-script']
        post_script = rtconfig['post-script']
        if self.tdef.run_mode == 'dummy':
            # Use dummy script items in dummy mode.
            script = rtconfig['dummy mode']['script']
            if rtconfig['dummy mode']['disable pre-script']:
                pre_script = None
            if rtconfig['dummy mode']['disable post-script']:
                post_script = None
        elif self.tdef.suite_polling_cfg:
            # Automatic suite state polling script
            comstr = "cylc suite-state " + \
                     " --task=" + self.tdef.suite_polling_cfg['task'] + \
                     " --point=" + str(self.point) + \
                     " --status=" + self.tdef.suite_polling_cfg['status']
            for key, fmt in [
                    ('user', ' --%s=%s'),
                    ('host', ' --%s=%s'),
                    ('interval', ' --%s=%d'),
                    ('max-polls', ' --%s=%s'),
                    ('run-dir', ' --%s=%s'),
                    ('template', ' --%s=%s')]:
                if rtconfig['suite state polling'][key]:
                    comstr += fmt % (key, rtconfig['suite state polling'][key])
            comstr += " " + self.tdef.suite_polling_cfg['suite']
            script = "echo " + comstr + "\n" + comstr
        return script, pre_script, post_script

    def _create_job_log_path(self):
        """Create job log directory, etc.

        Create local job directory, and NN symbolic link.
        If NN => 01, remove numbered directories with submit numbers greater
        than 01.
        Return a string in the form "POINT/NAME/SUBMIT_NUM".

        """
        job_file_dir = self.get_job_log_path(self.HEAD_MODE_LOCAL)
        task_log_dir = os.path.dirname(job_file_dir)
        if self.submit_num == 1:
            try:
                names = os.listdir(task_log_dir)
            except OSError:
                pass
            else:
                for name in names:
                    if name not in ["01", self.NN]:
                        rmtree(
                            os.path.join(task_log_dir, name),
                            ignore_errors=True)
        else:
            rmtree(job_file_dir, ignore_errors=True)

        mkdir_p(job_file_dir)
        target = os.path.join(task_log_dir, self.NN)
        source = os.path.basename(job_file_dir)
        try:
            prev_source = os.readlink(target)
        except OSError:
            prev_source = None
        if prev_source == source:
            return
        try:
            if prev_source:
                os.unlink(target)
            os.symlink(source, target)
        except OSError as exc:
            if not exc.filename:
                exc.filename = target
            raise exc

    def check_submission_timeout(self, now):
        """Check/handle submission timeout, called if TASK_STATUS_SUBMITTED."""
        timeout = self.state.submission_timer_timeout
        if timeout is None or now <= timeout:
            return False
        # Extend timeout so the job can be polled again at next timeout
        # just in case the job is still stuck in a queue
        msg = 'job submitted %s ago, but has not started' % (
            get_seconds_as_interval_string(
                timeout - self.summary['submitted_time']))
        self.state.submission_timer_timeout = None
        self.log(WARNING, msg)
        self.setup_event_handlers('submission timeout', msg)
        return True

    def check_execution_timeout(self, now):
        """Check/handle execution timeout, called if TASK_STATUS_RUNNING."""
        timeout = self.state.execution_timer_timeout
        if timeout is None or now <= timeout:
            return False
        if self.summary['execution_time_limit']:
            try_state = self.execution_time_limit_poll_timer
            if not try_state.is_timeout_set():
                try_state.next()
            if not try_state.is_delay_done():
                # Don't poll
                return False
            if self.execution_time_limit_poll_timer.next() is not None:
                # Poll now, and more retries lined up
                return True
        # No more retry lined up, issue execution timeout event
        msg = 'job started %s ago, but has not finished' % (
            get_seconds_as_interval_string(
                timeout - self.summary['started_time']))
        self.state.execution_timer_timeout = None
        self.log(WARNING, msg)
        self.setup_event_handlers('execution timeout', msg)
        return True

    def sim_time_check(self):
        """Check simulation time."""
        timeout = self.summary['started_time'] + self.sim_mode_run_length
        if time.time() > timeout:
            if self.tdef.rtconfig['simulation mode']['simulate failure']:
                self.message_queue.put(
                    self.identity, 'NORMAL', TASK_STATUS_SUBMITTED)
                self.message_queue.put(
                    self.identity, 'CRITICAL', TASK_STATUS_FAILED)
            else:
                self.message_queue.put(
                    self.identity, 'NORMAL', TASK_STATUS_SUBMITTED)
                self.message_queue.put(
                    self.identity, 'NORMAL', TASK_STATUS_SUCCEEDED)
            return True
        else:
            return False

    def reject_if_failed(self, message):
        """Reject a message if in the failed state.

        Handle 'enable resurrection' mode.

        """
        if self.state.status == TASK_STATUS_FAILED:
            if self.tdef.rtconfig['enable resurrection']:
                self.log(
                    WARNING,
                    'message receive while failed:' +
                    ' I am returning from the dead!'
                )
                return False
            else:
                self.log(
                    WARNING,
                    'rejecting a message received while in the failed state:'
                )
                self.log(WARNING, '  ' + message)
            return True
        else:
            return False

    def process_incoming_message(
            self, priority, message, polled_event_time=None):
        """Parse an incoming task message and update task state.

        Incoming is e.g. "succeeded at <TIME>".

        Correctly handle late (out of order) message which would otherwise set
        the state backward in the natural order of events.

        """
        is_polled = polled_event_time is not None

        # Log incoming messages with '>' to distinguish non-message log entries
        log_message = '(current:%s)> %s' % (self.state.status, message)
        if polled_event_time is not None:
            log_message += ' %s' % self.POLLED_INDICATOR
        self.log(self.LOGGING_LVL_OF.get(priority, INFO), log_message)

        # Strip the "at TIME" suffix.
        event_time = polled_event_time
        if not event_time:
            match = self.RE_MESSAGE_TIME.match(message)
            if match:
                message, event_time = match.groups()
        if not event_time:
            event_time = get_current_time_string()

        # always update the suite state summary for latest message
        self.summary['latest_message'] = message
        if is_polled:
            self.summary['latest_message'] += " %s" % self.POLLED_INDICATOR
        flags.iflag = True

        if self.reject_if_failed(message):
            # Failed tasks do not send messages unless declared resurrectable
            return

        # Check registered outputs.
        self.state.record_output(message, is_polled)

        if is_polled and self.state.status not in TASK_STATUSES_ACTIVE:
            # A poll result can come in after a task finishes.
            self.log(WARNING, "Ignoring late poll result: task is not active")
            return

        if priority == TaskMessage.WARNING:
            self.setup_event_handlers('warning', message, db_update=False)

        if (message == TASK_OUTPUT_STARTED and
                self.state.status in [TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
                                      TASK_STATUS_SUBMIT_FAILED]):
            if self.job_vacated:
                self.job_vacated = False
                self.log(WARNING, "Vacated job restarted: " + message)
            # Received a 'task started' message
            flags.pflag = True
            self.state.set_executing()
            self.summary['started_time'] = float(
                get_unix_time_from_time_string(event_time))
            self.summary['started_time_string'] = event_time
            self.db_updates_map[self.TABLE_TASK_JOBS].append({
                "time_run": self.summary['started_time_string']})
            if self.summary['execution_time_limit']:
                execution_timeout = self.summary['execution_time_limit']
            else:
                execution_timeout = self._get_events_conf('execution timeout')
            if execution_timeout:
                self.state.execution_timer_timeout = (
                    self.summary['started_time'] + execution_timeout)
            else:
                self.state.execution_timer_timeout = None

            # submission was successful so reset submission try number
            self.sub_try_state.num = 0
            self.setup_event_handlers('started', 'job started')
            self._set_next_poll_time('execution')

        elif (message == TASK_OUTPUT_SUCCEEDED and
                self.state.status in [
                    TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
                    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_RUNNING,
                    TASK_STATUS_FAILED]):
            # Received a 'task succeeded' message
            self.state.execution_timer_timeout = None
            self.state.hold_on_retry = False
            flags.pflag = True
            self.summary['finished_time'] = float(
                get_unix_time_from_time_string(event_time))
            self.summary['finished_time_string'] = event_time
            self.db_updates_map[self.TABLE_TASK_JOBS].append({
                "run_status": 0,
                "time_run_exit": self.summary['finished_time_string'],
            })
            # Update mean elapsed time only on task succeeded.
            if self.summary['started_time'] is not None:
                self.tdef.elapsed_times.append(
                    self.summary['finished_time'] -
                    self.summary['started_time'])
            self.setup_event_handlers("succeeded", "job succeeded")
            self.state.set_execution_succeeded(is_polled)

        elif (message == TASK_OUTPUT_FAILED and
                self.state.status in [
                    TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
                    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_RUNNING]):
            # (submit- states in case of very fast submission and execution).
            self.job_execution_failed(event_time)

        elif message.startswith(TaskMessage.FAIL_MESSAGE_PREFIX):
            # capture and record signals sent to task proxy
            self.db_events_insert(event="signaled", message=message)
            signal = message.replace(TaskMessage.FAIL_MESSAGE_PREFIX, "")
            self.db_updates_map[self.TABLE_TASK_JOBS].append(
                {"run_signal": signal})

        elif message.startswith(TaskMessage.VACATION_MESSAGE_PREFIX):
            flags.pflag = True
            self.state.set_state(TASK_STATUS_SUBMITTED)
            self.db_events_insert(event="vacated", message=message)
            self.state.execution_timer_timeout = None
            self.summary['started_time'] = None
            self.summary['started_time_string'] = None
            self.sub_try_state.num = 0
            self.job_vacated = True

        elif message == "submission failed":
            # This can arrive via a poll.
            self.state.submission_timer_timeout = None
            self.job_submission_failed(event_time)

        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            self.log(DEBUG, '(current: %s) unhandled: %s' % (
                self.state.status, message))
            if priority in [CRITICAL, ERROR, WARNING, INFO, DEBUG]:
                priority = getLevelName(priority)
            self.db_events_insert(
                event=("message %s" % str(priority).lower()), message=message)

    def spawn(self, state):
        """Spawn the successor of this task proxy."""
        self.has_spawned = True
        next_point = self.next_point()
        if next_point:
            return TaskProxy(
                self.tdef, next_point, state, False, self.stop_point,
                message_queue=self.message_queue)
        else:
            # next_point instance is out of the sequence bounds
            return None

    def ready_to_spawn(self):
        """Return True if ready to spawn my next-cycle successor.

        A task proxy is never ready to spawn if:
           * it has spawned already
           * its state is submit-failed (avoid running multiple instances
             of a task with bad job submission config).
        Otherwise a task proxy is ready to spawn if either:
           * self.tdef.spawn ahead is True (results in spawning out to max
             active cycle points), OR
           * its state is >= submitted (allows successive instances
             to run concurrently, but not out of order).
        """
        if (self.has_spawned or
                self.state.status == TASK_STATUS_SUBMIT_FAILED):
            return False
        else:
            return (self.tdef.spawn_ahead or
                    self.state.is_greater_than(TASK_STATUS_READY))

    def get_state_summary(self):
        """Return a dict containing the state summary of this task proxy."""
        self.summary['state'] = self.state.status
        self.summary['spawned'] = str(self.has_spawned)
        self.summary['mean_elapsed_time'] = (
            float(sum(self.tdef.elapsed_times)) /
            max(len(self.tdef.elapsed_times), 1))
        return self.summary

    def next_point(self):
        """Return the next cycle point."""
        p_next = None
        adjusted = []
        for seq in self.tdef.sequences:
            nxt = seq.get_next_point(self.point)
            if nxt:
                # may be None if beyond the sequence bounds
                adjusted.append(nxt)
        if adjusted:
            p_next = min(adjusted)
        return p_next

    def get_job_log_path(self, head_mode=None, submit_num=None, tail=None):
        """Return the job log path."""
        args = [str(self.point), self.tdef.name]
        if submit_num is None:
            submit_num = self.submit_num
        try:
            submit_num = "%02d" % submit_num
        except TypeError:
            pass
        if submit_num:
            args.append(submit_num)
        if head_mode == self.HEAD_MODE_LOCAL:
            args.insert(0, GLOBAL_CFG.get_derived_host_item(
                self.suite_name, "suite job log directory"))
        elif head_mode == self.HEAD_MODE_REMOTE:
            args.insert(0, GLOBAL_CFG.get_derived_host_item(
                self.suite_name, 'suite job log directory',
                self.task_host, self.task_owner))
        if tail:
            args.append(tail)
        return os.path.join(*args)

    def check_poll_ready(self, now=None):
        """Check if it is the next poll time."""
        return (
            self.state.status == TASK_STATUS_SUBMITTED and (
                self.check_submission_timeout(now) or
                self._check_poll_timer('submission', now)
            )
        ) or (
            self.state.status == TASK_STATUS_RUNNING and (
                self.check_execution_timeout(now) or
                self._check_poll_timer('execution', now)
            )
        )

    def _check_poll_timer(self, key, now=None):
        """Set the next execution/submission poll time."""
        timer = self.poll_timers.get(key)
        if timer is not None and timer.is_delay_done(now):
            self._set_next_poll_time(key)
            return True
        else:
            return False

    def _set_next_poll_time(self, key):
        """Set the next execution/submission poll time."""
        timer = self.poll_timers.get(key)
        if timer is not None:
            if timer.num is None:
                timer.num = 0
            delay = timer.next(no_exhaust=True)
            if delay is not None:
                self.log(INFO, 'next job poll in %s (after %s)' % (
                    timer.delay_as_seconds(), timer.timeout_as_str()))

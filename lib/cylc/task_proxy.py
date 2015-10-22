#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
from logging import getLogger, CRITICAL, ERROR, WARNING, INFO, DEBUG
import os
from pipes import quote
import Queue
from random import randrange
import re
import socket
import shlex
from shutil import rmtree
import time
import traceback

from isodatetime.timezone import get_local_time_zone

from cylc.mkdir_p import mkdir_p
from cylc.task_state import task_state
from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.cycling.iso8601
from cylc.cycling.loader import get_interval_cls, get_point_relative
from cylc.envvar import expandvars
import cylc.flags as flags
from cylc.wallclock import (
    get_current_time_string,
    get_time_string_from_unix_time,
    get_seconds_as_interval_string,
    RE_DATE_TIME_FORMAT_EXTENDED
)
from cylc.network.task_msgqueue import TaskMessageServer
from cylc.host_select import get_task_host
from cylc.job_file import JOB_FILE
from cylc.job_host import RemoteJobHostManager
from cylc.batch_sys_manager import BATCH_SYS_MANAGER
from cylc.outputs import outputs
from cylc.owner import is_remote_user, user
from cylc.poll_timer import PollTimer
from cylc.prerequisite import Prerequisite
from cylc.suite_host import is_remote_host, get_suite_host
from parsec.util import pdeepcopy, poverride
from parsec.OrderedDict import OrderedDictWithDefaults
from cylc.mp_pool import SuiteProcPool, SuiteProcContext
from cylc.rundb import CylcSuiteDAO
from cylc.task_id import TaskID
from cylc.task_message import TaskMessage
from cylc.task_output_logs import logfiles
from parsec.util import pdeepcopy, poverride
from parsec.config import ItemNotFoundError


CustomTaskEventHandlerContext = namedtuple(
    "CustomTaskEventHandlerContext",
    ["key", "ctx_type", "cmd"])


TaskEventMailContext = namedtuple(
    "TaskEventMailContext",
    ["key", "ctx_type", "event", "mail_from", "mail_to", "mail_smtp"])


TaskJobLogsRetrieveContext = namedtuple(
    "TaskJobLogsRetrieveContext",
    ["key", "ctx_type", "user_at_host", "max_size"])


class TryState(object):
    """Represent the current state of a (re)try."""

    def __init__(self, ctx=None, delays=None):
        self.ctx = ctx
        if delays:
            self.delays = list(delays)
        else:
            self.delays = [0]
        self.num = 0
        self.delay = None
        self.timeout = None
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

    def next(self):
        """Return the next retry delay if there is one, or None otherwise."""
        try:
            self.delay = self.delays[self.num]
        except IndexError:
            return None
        else:
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

    # Format string for single line output
    JOB_LOG_FMT_1 = "%(timestamp)s [%(cmd_key)s %(attr)s] %(mesg)s"
    # Format string for multi-line output
    JOB_LOG_FMT_M = "%(timestamp)s [%(cmd_key)s %(attr)s]\n\n%(mesg)s\n"

    CUSTOM_EVENT_HANDLER = "event-handler"
    EVENT_MAIL = "event-mail"
    JOB_KILL = "job-kill"
    JOB_LOGS_RETRIEVE = "job-logs-retrieve"
    JOB_POLL = "job-poll"
    JOB_SUBMIT = SuiteProcPool.JOB_SUBMIT
    MESSAGE_SUFFIX_RE = re.compile(
        ' at (' + RE_DATE_TIME_FORMAT_EXTENDED + '|unknown-time)$')

    LOGGING_LVL_OF = {
        "INFO": INFO,
        "NORMAL": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
        "DEBUG": DEBUG,
    }

    TABLE_TASK_JOBS = CylcSuiteDAO.TABLE_TASK_JOBS
    TABLE_TASK_JOB_LOGS = CylcSuiteDAO.TABLE_TASK_JOB_LOGS
    TABLE_TASK_EVENTS = CylcSuiteDAO.TABLE_TASK_EVENTS
    TABLE_TASK_STATES = CylcSuiteDAO.TABLE_TASK_STATES

    event_handler_env = {}
    stop_sim_mode_job_submission = False

    @classmethod
    def get_job_log_dir(
            cls, task_name, task_point, submit_num="NN", suite=None):
        """Return the latest job log path on the suite host."""
        try:
            submit_num = "%02d" % submit_num
        except TypeError:
            pass
        if suite:
            return os.path.join(
                GLOBAL_CFG.get_derived_host_item(
                    suite, "suite job log directory"),
                str(task_point), task_name, submit_num)
        else:
            return os.path.join(str(task_point), task_name, submit_num)

    def __init__(
            self, tdef, start_point, initial_state, stop_point=None,
            is_startup=False, validate_mode=False, submit_num=0,
            is_reload=False):
        self.tdef = tdef
        if submit_num is None:
            self.submit_num = 0
        else:
            self.submit_num = submit_num
        self.validate_mode = validate_mode

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

        self.prerequisites = []
        self.suicide_prerequisites = []
        self._add_prerequisites(self.point)
        self.point_as_seconds = None

        self.logfiles = logfiles()
        for lfile in self.tdef.rtconfig['extra log files']:
            self.logfiles.add_path(lfile)

        # outputs
        self.outputs = outputs(self.identity)
        for outp in self.tdef.outputs:
            msg = outp.get(self.point)
            if not self.outputs.exists(msg):
                self.outputs.add(msg)
        self.outputs.register()

        self.external_triggers = {}
        for ext in self.tdef.external_triggers:
            # set unsatisfied
            self.external_triggers[ext] = False

        # Manually inserted tasks may have a final cycle point set.
        self.stop_point = stop_point

        self.job_conf = None
        self.state = task_state(initial_state)
        self.state_before_held = None  # state before being held
        self.hold_on_retry = False
        self.manual_trigger = False
        self.is_manual_submit = False

        self.submission_timer_timeout = None
        self.execution_timer_timeout = None

        self.submitted_time = None
        self.started_time = None
        self.finished_time = None
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
            'logfiles': self.logfiles.get_paths()
        }
        self.job_file_written = False

        self.retries_configured = False

        self.run_try_state = TryState()
        self.sub_try_state = TryState()
        self.event_handler_try_states = {}

        self.message_queue = TaskMessageServer()
        self.db_inserts_map = {
            self.TABLE_TASK_JOBS: [],
            self.TABLE_TASK_JOB_LOGS: [],
            self.TABLE_TASK_STATES: [],
            self.TABLE_TASK_EVENTS: [],
        }
        self.db_updates_map = {
            self.TABLE_TASK_JOBS: [],
            self.TABLE_TASK_STATES: [],
        }

        # TODO - should take suite name from config!
        self.suite_name = os.environ['CYLC_SUITE_NAME']

        # In case task owner and host are needed by _db_events_insert()
        # for pre-submission events, set their initial values as if
        # local (we can't know the correct host prior to this because
        # dynamic host selection could be used).
        self.task_host = 'localhost'
        self.task_owner = None
        self.user_at_host = self.task_host

        self.submit_method_id = None
        self.batch_sys_name = None
        self.job_vacated = False

        self.submission_poll_timer = None
        self.execution_poll_timer = None

        self.logger = getLogger("main")

        # An initial db state entry is created at task proxy init. On reloading
        # or restarting the suite, the task proxies already have this db entry.
        if not self.validate_mode and not is_reload and self.submit_num == 0:
            self.db_inserts_map[self.TABLE_TASK_STATES].append({
                "time_created": get_current_time_string(),
                "time_updated": get_current_time_string(),
                "try_num": self.run_try_state.num + 1,
                "status": self.state.get_status()})

        if not self.validate_mode and self.submit_num > 0:
            self.db_updates_map[self.TABLE_TASK_STATES].append({
                "time_updated": get_current_time_string(),
                "status": self.state.get_status()})

        self.reconfigure_me = False
        self.event_hooks = None
        self.sim_mode_run_length = None
        self.set_from_rtconfig()
        self.delayed_start_str = None
        self.delayed_start = None
        self.expire_time_str = None
        self.expire_time = None

        self.kill_failed = False

    def _add_prerequisites(self, point):
        """Add task prerequisites."""
        # self.triggers[sequence] = [triggers for sequence]
        # Triggers for sequence_i only used if my cycle point is a
        # valid member of sequence_i's sequence of cycle points.

        for sequence, exps in self.tdef.triggers.items():
            for ctrig, exp in exps:
                key = ctrig.keys()[0]
                if not sequence.is_valid(self.point):
                    # This trigger is not valid for current cycle (see NOTE
                    # just above)
                    continue

                cpre = Prerequisite(self.identity, self.tdef.start_point)
                for label in ctrig:
                    trig = ctrig[label]
                    if trig.graph_offset_string is not None:
                        prereq_offset_point = get_point_relative(
                                trig.graph_offset_string, point)
                        if prereq_offset_point > point:
                            prereq_offset = prereq_offset_point - point
                            if (self.tdef.max_future_prereq_offset is None or
                                    prereq_offset > self.tdef.max_future_prereq_offset):
                                self.tdef.max_future_prereq_offset = prereq_offset
                        cpre.add(trig.get_prereq(point)[0], label,
                                 prereq_offset_point < self.tdef.start_point)
                    else:
                        cpre.add(trig.get_prereq(point)[0], label)
                cpre.set_condition(exp)
                if ctrig[key].suicide:
                    self.suicide_prerequisites.append(cpre)
                else:
                    self.prerequisites.append(cpre)

        if self.tdef.sequential:
            # Add a previous-instance prerequisite, adjust cleanup cutoff.
            p_next = None
            adjusted = []
            for seq in self.tdef.sequences:
                nxt = seq.get_next_point(self.point)
                if nxt:
                    # may be None if beyond the sequence bounds
                    adjusted.append(nxt)
            if adjusted:
                p_next = min(adjusted)
                if (self.cleanup_cutoff is not None and
                        self.cleanup_cutoff < p_next):
                    self.cleanup_cutoff = p_next
            p_prev = None
            adjusted = []
            for seq in self.tdef.sequences:
                prv = seq.get_nearest_prev_point(self.point)
                if prv:
                    # None if out of sequence bounds.
                    adjusted.append(prv)
            if adjusted:
                p_prev = max(adjusted)
                cpre = Prerequisite(self.identity, self.tdef.start_point)
                prereq = TaskID.get(self.tdef.name, p_prev) + ' succeeded'
                label = self.tdef.name
                cpre.add(prereq, label, p_prev < self.tdef.start_point)
                cpre.set_condition(label)
                self.prerequisites.append(cpre)

    def _get_events_conf(self, key, default=None):
        """Return an events setting from suite then global configuration."""
        for getter in (
                self.tdef.rtconfig["events"],
                self.event_hooks,
                GLOBAL_CFG.get()["task events"]):
            try:
                value = getter.get(key)
                if value is not None:
                    return value
            except (ItemNotFoundError, KeyError):
                pass
        return default

    def _get_host_conf(self, key, default=None):
        """Return a host setting from suite then global configuration."""
        if self.tdef.rtconfig["remote"].get(key):
            return self.tdef.rtconfig["remote"][key]
        else:
            try:
                return GLOBAL_CFG.get_host_item(
                    key, self.task_host, self.task_owner)
            except ItemNotFoundError:
                pass
        return default

    def log(self, lvl=INFO, msg=""):
        """Log a message of this task proxy."""
        msg = "[%s] -%s" % (self.identity, msg)
        self.logger.log(lvl, msg)

    def command_log(self, ctx):
        """Log an activity for a job of this task proxy."""
        ctx_str = str(ctx)
        if not ctx_str:
            return
        submit_num = "NN"
        if isinstance(ctx.cmd_key, tuple):  # An event handler
            submit_num = ctx.cmd_key[-1]
        job_log_dir = self.get_job_log_dir(
            self.tdef.name, self.point, submit_num, self.suite_name)
        job_activity_log = os.path.join(job_log_dir, "job-activity.log")
        with open(job_activity_log, "ab") as handle:
            handle.write(ctx_str)
        if ctx.cmd and ctx.ret_code:
            self.log(ERROR, ctx_str)
        elif ctx.cmd:
            self.log(DEBUG, ctx_str)

    def _db_events_insert(self, event="", message=""):
        """Record an event to the DB."""
        self.db_inserts_map[self.TABLE_TASK_EVENTS].append({
            "time": get_current_time_string(),
            "event": event,
            "message": message,
            "misc": self.user_at_host})

    def retry_delay_done(self):
        """Is retry delay done? Can I retry now?"""
        now = time.time()
        return (self.run_try_state.is_delay_done(now) or
                self.sub_try_state.is_delay_done(now))

    def ready_to_run(self):
        """Is this task ready to run?"""
        ready = (
            (
                self.state.is_currently('queued') or
                (
                    self.state.is_currently('waiting') and
                    self.prerequisites_are_all_satisfied() and
                    all(self.external_triggers.values())
                ) or
                (
                    self.state.is_currently('submit-retrying', 'retrying') and
                    self.retry_delay_done()
                )
            ) and self.start_time_reached()
        )
        if ready and self.has_expired():
            self.log(WARNING, 'Task expired (skipping job).')
            self.setup_event_handlers(
                'expired', 'Task expired (skipping job).')
            self.reset_state_expired()
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

    def get_offset_as_seconds(self, offset):
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

    def has_expired(self):
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

    def get_resolved_dependencies(self):
        """Report who I triggered off."""
        satby = {}
        for req in self.prerequisites:
            satby.update(req.satisfied_by)
        dep = satby.values()
        # order does not matter here; sort to allow comparison with
        # reference run task with lots of near-simultaneous triggers.
        dep.sort()
        return dep

    def unset_outputs(self):
        """Remove special output messages.

        These are added for use in triggering off special states:
          failed, submit-failed, expired
        If the task state is later reset, these must be removed or they will
        seen as incomplete outputs when the task finishes.
        """
        self.hold_on_retry = False
        self.kill_failed = False
        for state in ["failed", "submit-failed", "expired"]:
            msg = "%s %s" % (self.identity, state)
            if self.outputs.exists(msg):
                self.outputs.remove(msg)

    def turn_off_timeouts(self):
        """Turn off submission and execution timeouts."""
        self.submission_timer_timeout = None
        self.execution_timer_timeout = None

    def prerequisites_get_target_points(self):
        """Return a list of cycle points targetted by each prerequisite."""
        points = []
        for preq in self.prerequisites:
            points += preq.get_target_points()
        return points

    def prerequisites_dump(self):
        res = []
        for preq in self.prerequisites:
            res += preq.dump()
        return res

    def prerequisites_eval_all(self):
        # (Validation: will abort on illegal trigger expressions.)
        for preqs in [self.prerequisites, self.suicide_prerequisites]:
            for preq in preqs:
                preq.is_satisfied()

    def prerequisites_are_all_satisfied(self):
        return all(preq.is_satisfied() for preq in self.prerequisites)

    def suicide_prerequisites_are_all_satisfied(self):
        return all(preq.is_satisfied() for preq in self.suicide_prerequisites)

    def set_prerequisites_all_satisfied(self):
        for prereq in self.prerequisites:
            prereq.set_satisfied()

    def set_prerequisites_not_satisfied(self):
        for prereq in self.prerequisites:
            prereq.set_not_satisfied()

    def reset_state_ready(self):
        """Reset state to "ready"."""
        self.set_status('waiting')
        self._db_events_insert(event="reset to ready")
        self.set_prerequisites_all_satisfied()
        self.unset_outputs()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()

    def reset_state_expired(self):
        """Reset state to "expired"."""
        self.set_status('expired')
        self._db_events_insert(event="reset to expired")
        self.set_prerequisites_all_satisfied()
        self.unset_outputs()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()
        self.outputs.add(self.identity + ' expired', completed=True)

    def reset_state_waiting(self):
        """Reset state to "waiting".

        Waiting and all prerequisites UNsatisified.

        """
        self.set_status('waiting')
        self._db_events_insert(event="reset to waiting")
        self.set_prerequisites_not_satisfied()
        self.unset_outputs()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()

    def reset_state_succeeded(self):
        """Reset state to succeeded.

        All prerequisites satisified and all outputs complete.

        """
        self.set_status('succeeded')
        self._db_events_insert(event="reset to succeeded")
        self.set_prerequisites_all_satisfied()
        self.unset_outputs()
        self.turn_off_timeouts()
        # TODO - for message outputs this should be optional (see #1551):
        self.outputs.set_all_completed()

    def reset_state_failed(self):
        """Reset state to "failed".

        All prerequisites satisified and no outputs complete

        """
        self.set_status('failed')
        self._db_events_insert(event="reset to failed")
        self.set_prerequisites_all_satisfied()
        self.hold_on_retry = False
        self.outputs.set_all_incomplete()
        # set a new failed output just as if a failure message came in
        self.turn_off_timeouts()
        self.outputs.add(self.identity + ' failed', completed=True)

    def reset_state_held(self):
        """Reset state to "held"."""
        if self.state.is_currently(
                'waiting', 'queued', 'submit-retrying', 'retrying'):
            self.state_before_held = task_state(self.state.get_status())
            self.set_status('held')
            self.turn_off_timeouts()
            self._db_events_insert(event="reset to held")
            self.log(INFO, '%s => held' % self.state_before_held.get_status())
        elif self.is_active():
            self.hold_on_retry = True

    def reset_state_unheld(self, stop_point=None):
        """Reset state to state before being "held".

        If stop_point is not None, don't release task if it is beyond the stop
        cycle point.

        """
        self.hold_on_retry = False
        if (not self.state.is_currently('held') or
                stop_point and self.point > stop_point):
            return
        if self.state_before_held is None:
            return self.reset_state_waiting()
        old_status = self.state_before_held.get_status()
        self.set_status(old_status)
        self.state_before_held = None
        self._db_events_insert(event="reset to %s" % (old_status))
        self.log(INFO, 'held => %s' % (old_status))

    def job_submission_callback(self, result):
        """Callback on job submission."""
        if result.out is not None:
            out = ""
            for line in result.out.splitlines(True):
                if line.startswith(
                        BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID + "="):
                    self.submit_method_id = line.strip().replace(
                        BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID + "=", "")
                else:
                    out += line
            result.out = out
        self.command_log(result)

        if result.ret_code == SuiteProcPool.JOB_SKIPPED_FLAG:
            return

        if self.submit_method_id and result.ret_code == 0:
            self.job_submission_succeeded()
        else:
            self.job_submission_failed()

    def job_poll_callback(self, line):
        """Callback on job poll."""
        ctx = SuiteProcContext(self.JOB_POLL, None)
        ctx.out = line
        ctx.ret_code = 0
        self.command_log(ctx)

        items = line.split("|")
        # See cylc.batch_sys_manager.JobPollContext
        try:
            (
                batch_sys_exit_polled, run_status, run_signal, _, time_run
            ) = items[4:9]
        except IndexError:
            self.summary['latest_message'] = 'poll failed'
            return
        if run_status == "1" and run_signal in ["ERR", "EXIT"]:
            # Failed normally
            self._process_poll_message(INFO, TaskMessage.FAILED)
        elif run_status == "1" and batch_sys_exit_polled == "1":
            # Failed by a signal, and no longer in batch system
            self._process_poll_message(INFO, TaskMessage.FAILED)
            self._process_poll_message(
                INFO, TaskMessage.FAIL_MESSAGE_PREFIX + run_signal)
        elif run_status == "1":
            # The job has terminated, but is still managed by batch system.
            # Some batch system may restart a job in this state, so don't
            # mark as failed yet.
            self._process_poll_message(INFO, TaskMessage.STARTED)
        elif run_status == "0":
            # The job succeeded
            self._process_poll_message(INFO, TaskMessage.SUCCEEDED)
        elif time_run and batch_sys_exit_polled == "1":
            # The job has terminated without executing the error trap
            self._process_poll_message(INFO, TaskMessage.FAILED)
        elif time_run:
            # The job has started, and is still managed by batch system
            self._process_poll_message(INFO, TaskMessage.STARTED)
        elif batch_sys_exit_polled == "1":
            # The job never ran, and no longer in batch system
            self._process_poll_message(INFO, "submission failed")
        else:
            # The job never ran, and is in batch system
            self._process_poll_message(INFO, "submitted")

    def _process_poll_message(self, priority, message):
        """Wraps self.process_incoming_message for poll messages."""
        self.process_incoming_message(
            (priority, "%s %s" % (self.identity, message)),
            msg_was_polled=True)

    def job_poll_message_callback(self, line):
        """Callback on job poll message."""
        ctx = SuiteProcContext(self.JOB_POLL, None)
        ctx.out = line
        ctx.ret_code = 0
        self.command_log(ctx)

        items = line.split("|")
        priority, message = line.split("|")[3:5]
        self.process_incoming_message((priority, message), msg_was_polled=True)

    def job_kill_callback(self, line):
        """Callback on job kill."""
        ctx = SuiteProcContext(self.JOB_KILL, None)
        ctx.timestamp, _, ctx.ret_code = line.split("|", 2)
        ctx.out = line
        ctx.ret_code = int(ctx.ret_code)
        self.command_log(ctx)
        if ctx.ret_code:  # non-zero exit status
            self.summary['latest_message'] = 'kill failed'
            self.log(WARNING, 'job(%02d) kill failed' % self.submit_num)
            flags.iflag = True
            self.kill_failed = True
        elif self.state.is_currently('submitted'):
            self.log(INFO, 'job(%02d) killed' % self.submit_num)
            self.job_submission_failed()
        elif self.state.is_currently('running'):
            self.log(INFO, 'job(%02d) killed' % self.submit_num)
            self.job_execution_failed()
        else:
            msg = ('ignoring job kill result, unexpected task state: %s'
                   % self.state.get_status())
            self.log(WARNING, msg)

    def job_submit_callback(self, line):
        """Callback on job submit."""
        ctx = SuiteProcContext(self.JOB_SUBMIT, None)
        items = line.split("|")
        ctx.timestamp, _, ctx.ret_code = items[0:3]
        ctx.out = line
        ctx.ret_code = int(ctx.ret_code)
        self.command_log(ctx)

        if ctx.ret_code == SuiteProcPool.JOB_SKIPPED_FLAG:
            return

        try:
            self.submit_method_id = items[3]
        except IndexError:
            self.submit_method_id = None
        if self.submit_method_id and ctx.ret_code == 0:
            self.job_submission_succeeded()
        else:
            self.job_submission_failed()

    def job_cmd_out_callback(self, line):
        """Callback on job command STDOUT/STDERR."""
        job_log_dir = self.get_job_log_dir(
            self.tdef.name, self.point, "NN", self.suite_name)
        job_activity_log = os.path.join(job_log_dir, "job-activity.log")
        with open(job_activity_log, "ab") as handle:
            if not line.endswith("\n"):
                line += "\n"
            handle.write(line)

    def setup_event_handlers(
            self, event, message, db_update=True, db_event=None, db_msg=None):
        """Set up event handlers."""
        # extra args for inconsistent use between events, logging, and db
        # updates
        db_event = db_event or event
        if db_update:
            self._db_events_insert(event=db_event, message=db_msg)

        if self.tdef.run_mode != 'live':
            return

        self.setup_job_logs_retrieval(event, message)
        self.setup_event_mail(event, message)
        self.setup_custom_event_handlers(event, message)

    def setup_job_logs_retrieval(self, event, _=None):
        """Set up remote job logs retrieval."""
        key1 = self.JOB_LOGS_RETRIEVE
        if ((key1, self.submit_num) in self.event_handler_try_states or
                event not in ["failed", "retry", "succeeded"]):
            return
        if (self.user_at_host in [user + '@localhost', 'localhost'] or
                not self._get_host_conf("retrieve job logs")):
            self.register_job_logs(self.submit_num)
            return
        self.event_handler_try_states[(key1, self.submit_num)] = TryState(
            TaskJobLogsRetrieveContext(
                key1,
                self.JOB_LOGS_RETRIEVE,  # ctx_type
                self.user_at_host,
                self._get_host_conf("retrieve job logs max size"),  # max_size
            ),
            self._get_host_conf("retrieve job logs retry delays", []))

    def setup_event_mail(self, event, message):
        """Event notification, by email."""
        key1 = (self.EVENT_MAIL, event)
        if ((key1, self.submit_num) in self.event_handler_try_states
                or event not in self._get_events_conf("mail events", [])):
            return

        self.event_handler_try_states[(key1, self.submit_num)] = TryState(
            TaskEventMailContext(
                key1,
                self.EVENT_MAIL,  # ctx_type
                event,
                self._get_events_conf(  # mail_from
                    "mail from",
                    "notifications@" + get_suite_host(),
                ),
                self._get_events_conf("mail to", user),  # mail_to
                self._get_events_conf("mail smtp"),  # mail_smtp
            ),
            self._get_events_conf("mail retry delays", []))

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
        env = None
        for i, handler in enumerate(handlers):
            key1 = (
                "%s-%02d" % (self.CUSTOM_EVENT_HANDLER, i),
                event)
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
            self.event_handler_try_states[(key1, self.submit_num)] = TryState(
                CustomTaskEventHandlerContext(
                    key1,
                    self.CUSTOM_EVENT_HANDLER,
                    cmd,
                ),
                retry_delays)

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

    def job_submission_failed(self):
        """Handle job submission failure."""
        self.log(ERROR, 'submission failed')
        self.db_updates_map[self.TABLE_TASK_JOBS].append({
            "time_submit_exit": get_current_time_string(),
            "submit_status": 1,
        })
        self.submit_method_id = None
        if self.sub_try_state.next() is None:
            # No submission retry lined up: definitive failure.
            flags.pflag = True
            outp = self.identity + " submit-failed"  # hack: see github #476
            self.outputs.add(outp)
            self.outputs.set_completed(outp)
            self.set_status('submit-failed')
            self.setup_event_handlers(
                'submission failed', 'job submission failed')
        else:
            # There is a submission retry lined up.
            timeout_str = self.sub_try_state.timeout_as_str()

            delay_msg = "submit-retrying in %s" % (
                self.sub_try_state.delay_as_seconds())
            msg = "submission failed, %s (after %s)" % (delay_msg, timeout_str)
            self.log(INFO, "job(%02d) " % self.submit_num + msg)
            self.summary['latest_message'] = msg
            self.summary['waiting for reload'] = self.reconfigure_me

            self.set_status('submit-retrying')
            self._db_events_insert(
                event="submission failed", message=delay_msg)
            self.set_prerequisites_all_satisfied()
            self.outputs.set_all_incomplete()

            # TODO - is this record is redundant with that in
            # setup_event_handlers?
            self._db_events_insert(
                event="submission failed",
                message="submit-retrying in " + str(self.sub_try_state.delay))
            self.setup_event_handlers(
                "submission retry", "job submission failed, " + delay_msg)
            if self.hold_on_retry:
                self.reset_state_held()

    def job_submission_succeeded(self):
        """Handle job submission succeeded."""
        if self.submit_method_id is not None:
            self.log(INFO, 'submit_method_id=' + self.submit_method_id)
        self.log(INFO, 'submission succeeded')
        now = get_current_time_string()
        self.db_updates_map[self.TABLE_TASK_STATES].append({
            "time_updated": now,
            "submit_method_id": self.submit_method_id})
        self.db_updates_map[self.TABLE_TASK_JOBS].append({
            "time_submit_exit": now,
            "submit_status": 0,
            "batch_sys_job_id": self.submit_method_id})
        if self.tdef.run_mode == 'simulation':
            if self.__class__.stop_sim_mode_job_submission:
                # Real jobs that are ready to run are queued to the proc pool
                # (i.e. the 'ready' state) but not submitted, before shutdown.
                self.set_status('ready')
            else:
                self.started_time = time.time()
                self.summary['started_time'] = self.started_time
                self.summary['started_time_string'] = (
                    get_time_string_from_unix_time(self.started_time))
                self.outputs.set_completed(self.identity + " started")
                self.set_status('running')
            return

        outp = self.identity + ' submitted'
        if not self.outputs.is_completed(outp):
            self.outputs.set_completed(outp)
            # Allow submitted tasks to spawn even if nothing else is happening.
            flags.pflag = True

        self.submitted_time = time.time()

        self.summary['started_time'] = None
        self.summary['started_time_string'] = None
        self.started_time = None
        self.summary['finished_time'] = None
        self.summary['finished_time_string'] = None
        self.finished_time = None

        self.summary['submitted_time'] = self.submitted_time
        self.summary['submitted_time_string'] = (
            get_time_string_from_unix_time(self.submitted_time))
        self.summary['submit_method_id'] = self.submit_method_id
        self.summary['latest_message'] = "submitted"
        self.setup_event_handlers(
            'submitted', 'job submitted', db_event='submission succeeded')

        if self.state.is_currently('ready'):
            # The 'started' message can arrive before this. In rare occassions,
            # the submit command of a batch system has sent the job to its
            # server, and the server has started the job before the job submit
            # command returns.
            self.set_status('submitted')
            submit_timeout = self._get_events_conf('submission timeout')
            if submit_timeout:
                self.submission_timer_timeout = (
                    self.submitted_time + submit_timeout
                )
            else:
                self.submission_timer_timeout = None
            self.submission_poll_timer.set_timer()

    def job_execution_failed(self):
        """Handle a job failure."""
        self.finished_time = time.time()  # TODO: use time from message
        self.summary['finished_time'] = self.finished_time
        self.summary['finished_time_string'] = (
            get_time_string_from_unix_time(self.finished_time))
        self.db_updates_map[self.TABLE_TASK_JOBS].append({
            "run_status": 1,
            "time_run_exit": self.summary['finished_time_string'],
        })
        self.execution_timer_timeout = None
        if self.run_try_state.next() is None:
            # No retry lined up: definitive failure.
            # Note the 'failed' output is only added if needed.
            flags.pflag = True
            msg = self.identity + ' failed'
            self.outputs.add(msg)
            self.outputs.set_completed(msg)
            self.set_status('failed')
            self.setup_event_handlers('failed', 'job failed')

        else:
            # There is a retry lined up
            timeout_str = self.run_try_state.timeout_as_str()
            delay_msg = "retrying in %s" % (
                self.run_try_state.delay_as_seconds())
            msg = "failed, %s (after %s)" % (delay_msg, timeout_str)
            self.log(INFO, "job(%02d) " % self.submit_num + msg)
            self.summary['latest_message'] = msg

            self.set_status('retrying')
            self.set_prerequisites_all_satisfied()
            self.outputs.set_all_incomplete()
            self.setup_event_handlers(
                "retry", "job failed, " + delay_msg, db_msg=delay_msg)
            if self.hold_on_retry:
                self.reset_state_held()

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
                self.run_try_state.delays = list(rtconfig['retry delays'])
                self.sub_try_state.delays = list(
                    rtconfig['job submission']['retry delays'])

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

        self.event_hooks = rtconfig['event hooks']

        self.submission_poll_timer = PollTimer(
            copy(rtconfig['submission polling intervals']),
            copy(GLOBAL_CFG.get(['submission polling intervals'])),
            'submission', self.log)

        self.execution_poll_timer = PollTimer(
            copy(rtconfig['execution polling intervals']),
            copy(GLOBAL_CFG.get(['execution polling intervals'])),
            'execution', self.log)

    def register_job_logs(self, submit_num):
        """Register job logs in the runtime database."""
        data = []
        has_job_out = False
        job_log_dir = self.get_job_log_dir(
            self.tdef.name, self.point, submit_num, self.suite_name)
        try:
            for filename in os.listdir(job_log_dir):
                try:
                    stat = os.stat(os.path.join(job_log_dir, filename))
                except OSError:
                    continue
                else:
                    data.append((stat.st_mtime, stat.st_size, filename))
                if filename == "job.out":
                    has_job_out = True
        except OSError:
            pass

        rel_job_log_dir = self.get_job_log_dir(
            self.tdef.name, self.point, submit_num)
        for mtime, size, filename in data:
            self.db_inserts_map[self.TABLE_TASK_JOB_LOGS].append({
                "submit_num": submit_num,
                "filename": filename,
                "location": os.path.join(rel_job_log_dir, filename),
                "mtime": mtime,
                "size": size})
        return has_job_out

    def prep_submit(self, dry_run=False, overrides=None):
        """Prepare job submission.

        Return self on a good preparation.

        """
        if self.tdef.run_mode == 'simulation' or (
                self.job_file_written and not dry_run):
            return self

        try:
            self._prep_submit_impl(overrides=overrides)
            JOB_FILE.write(self.job_conf)
            self.job_file_written = True
        except Exception, exc:
            # Could be a bad command template.
            if flags.debug:
                traceback.print_exc()
            self.command_log(SuiteProcContext(
                self.JOB_SUBMIT, '(prepare job file)', err=exc,
                ret_code=1))
            self.job_submission_failed()
            return

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
        self._db_events_insert(event="incrementing submit number")
        self.job_file_written = False

        local_job_log_dir, common_job_log_path = self._create_job_log_path(
            new_mode=True)
        local_jobfile_path = os.path.join(
            local_job_log_dir, common_job_log_path)

        rtconfig = pdeepcopy(self.tdef.rtconfig)
        poverride(rtconfig, overrides)

        self.set_from_rtconfig(rtconfig)

        # construct the job_sub_method here so that a new one is used if
        # the task is re-triggered by the suite operator - so it will
        # get new stdout/stderr logfiles and not overwrite the old ones.

        # dynamic instantiation - don't know job sub method till run time.
        self.batch_sys_name = rtconfig['job submission']['method']
        self.summary['batch_sys_name'] = self.batch_sys_name

        command = rtconfig['script']
        use_manual = rtconfig['manual completion']
        if self.tdef.run_mode == 'dummy':
            # (dummy tasks don't detach)
            use_manual = False
            command = rtconfig['dummy mode']['script']
            if rtconfig['dummy mode']['disable pre-script']:
                precommand = None
            if rtconfig['dummy mode']['disable post-script']:
                postcommand = None
        else:
            precommand = rtconfig['pre-script']
            postcommand = rtconfig['post-script']

        if self.tdef.suite_polling_cfg:
            # generate automatic suite state polling script
            comstr = "cylc suite-state " + \
                     " --task=" + self.tdef.suite_polling_cfg['task'] + \
                     " --point=" + str(self.point) + \
                     " --status=" + self.tdef.suite_polling_cfg['status']
            if rtconfig['suite state polling']['user']:
                comstr += " --user=" + rtconfig['suite state polling']['user']
            if rtconfig['suite state polling']['host']:
                comstr += " --host=" + rtconfig['suite state polling']['host']
            if rtconfig['suite state polling']['interval']:
                comstr += " --interval=" + str(int(
                    rtconfig['suite state polling']['interval']))
            if rtconfig['suite state polling']['max-polls']:
                comstr += (
                    " --max-polls=" +
                    str(rtconfig['suite state polling']['max-polls']))
            if rtconfig['suite state polling']['run-dir']:
                comstr += (
                    " --run-dir=" +
                    str(rtconfig['suite state polling']['run-dir']))
            comstr += " " + self.tdef.suite_polling_cfg['suite']
            command = "echo " + comstr + "\n" + comstr

        # Determine task host settings now, just before job submission,
        # because dynamic host selection may be used.

        # host may be None (= run task on suite host)
        self.task_host = get_task_host(rtconfig['remote']['host'])
        if self.task_host != "localhost":
            self.log(INFO, "Task host: " + self.task_host)

        self.task_owner = rtconfig['remote']['owner']

        if self.task_owner:
            self.user_at_host = self.task_owner + "@" + self.task_host
        else:
            self.user_at_host = self.task_host
        self.summary['host'] = self.user_at_host
        self.submission_poll_timer.set_host(self.task_host)
        self.execution_poll_timer.set_host(self.task_host)

        RemoteJobHostManager.get_inst().init_suite_run_dir(
            self.suite_name, self.user_at_host)

        self.db_updates_map[self.TABLE_TASK_STATES].append({
            "time_updated": get_current_time_string(),
            "submit_method": self.batch_sys_name,
            "host": self.user_at_host,
            "submit_num": self.submit_num})
        self._populate_job_conf(
            rtconfig, local_jobfile_path, common_job_log_path)
        self.job_conf.update({
            'use manual completion': use_manual,
            'pre-script': precommand,
            'script': command,
            'post-script': postcommand
            }.items()
        )
        self.db_inserts_map[self.TABLE_TASK_JOBS].append({
            "is_manual_submit": self.is_manual_submit,
            "try_num": self.run_try_state.num + 1,
            "time_submit": get_current_time_string(),
            "user_at_host": self.user_at_host,
            "batch_sys_name": self.batch_sys_name,
        })
        self.is_manual_submit = False

    def submit(self):
        """Submit a job for this task."""
        # The job file is now (about to be) used: reset the file write flag so
        # that subsequent manual retrigger will generate a new job file.
        self.job_file_written = False
        self.set_status('ready')
        # Send the job to the command pool.
        return self._run_job_command(
            self.JOB_SUBMIT,
            args=[self.job_conf['job file path']],
            callback=self.job_submission_callback,
            stdin_file_paths=[self.job_conf['local job file path']])

    def prep_manip(self):
        """A cut down version of prepare_submit().

        This provides access to job poll commands before the task is submitted,
        for polling in the submitted state or on suite restart.

        """
        if self.user_at_host:
            if "@" in self.user_at_host:
                self.task_owner, self.task_host = (
                    self.user_at_host.split('@', 1))
            else:
                self.task_host = self.user_at_host
        local_job_log_dir, common_job_log_path = self._create_job_log_path()
        local_jobfile_path = os.path.join(
            local_job_log_dir, common_job_log_path)
        rtconfig = pdeepcopy(self.tdef.rtconfig)
        self._populate_job_conf(
            rtconfig, local_jobfile_path, common_job_log_path)

    def _populate_job_conf(
            self, rtconfig, local_jobfile_path, common_job_log_path):
        """Populate the configuration for submitting or manipulating a job."""
        self.batch_sys_name = rtconfig['job submission']['method']
        self.job_conf = OrderedDictWithDefaults({
            'suite name': self.suite_name,
            'task id': self.identity,
            'batch system name': rtconfig['job submission']['method'],
            'directives': rtconfig['directives'],
            'init-script': rtconfig['init-script'],
            'env-script': rtconfig['env-script'],
            'runtime environment': rtconfig['environment'],
            'remote suite path': (
                rtconfig['remote']['suite definition directory']),
            'job script shell': rtconfig['job submission']['shell'],
            'batch submit command template': (
                rtconfig['job submission']['command template']),
            'work sub-directory': rtconfig['work sub-directory'],
            'use manual completion': False,
            'pre-script': '',
            'script': '',
            'post-script': '',
            'namespace hierarchy': self.tdef.namespace_hierarchy,
            'submission try number': self.sub_try_state.num + 1,
            'try number': self.run_try_state.num + 1,
            'absolute submit number': self.submit_num,
            'is cold-start': self.tdef.is_coldstart,
            'owner': self.task_owner,
            'host': self.task_host,
            'log files': self.logfiles,
            'common job log path': common_job_log_path,
            'local job file path': local_jobfile_path,
            'job file path': local_jobfile_path,
        }.items())

        log_files = self.job_conf['log files']
        log_files.add_path(local_jobfile_path)

        if not self.job_conf['host']:
            self.job_conf['host'] = socket.gethostname()

        if (is_remote_host(self.job_conf['host']) or
                is_remote_user(self.job_conf['owner'])):
            remote_job_log_dir = GLOBAL_CFG.get_derived_host_item(
                self.suite_name,
                'suite job log directory',
                self.task_host,
                self.task_owner)

            remote_path = os.path.join(
                remote_job_log_dir, self.job_conf['common job log path'])

            # Used in command construction:
            self.job_conf['job file path'] = remote_path

            # Record paths of remote log files for access by gui
            # N.B. Need to consider remote log files in shared file system
            #      accessible from the suite daemon, mounted under the same
            #      path or otherwise.
            prefix = self.job_conf['host'] + ':' + remote_path
            if self.job_conf['owner']:
                prefix = self.job_conf['owner'] + "@" + prefix
            log_files.add_path(prefix + '.out')
            log_files.add_path(prefix + '.err')
        else:
            # interpolate environment variables in extra logs
            for idx in range(len(log_files.paths)):
                log_files.paths[idx] = expandvars(log_files.paths[idx])

            # Record paths of local log files for access by gui
            log_files.add_path(self.job_conf['job file path'] + '.out')
            log_files.add_path(self.job_conf['job file path'] + '.err')

    def handle_submission_timeout(self):
        """Handle submission timeout, only called if in "submitted" state."""
        msg = 'job submitted %s ago, but has not started' % (
            get_seconds_as_interval_string(
                self.event_hooks['submission timeout'])
        )
        self.log(WARNING, msg)
        self.setup_event_handlers('submission timeout', msg)

    def handle_execution_timeout(self):
        """Handle execution timeout, only called if in "running" state."""
        if self.event_hooks['reset timer']:
            # the timer is being re-started by put messages
            msg = 'last message %s ago, but job not finished'
        else:
            msg = 'job started %s ago, but has not finished'
        msg = msg % get_seconds_as_interval_string(
            self.event_hooks['execution timeout'])
        self.log(WARNING, msg)
        self.setup_event_handlers('execution timeout', msg)

    def sim_time_check(self):
        """Check simulation time."""
        timeout = self.started_time + self.sim_mode_run_length
        if time.time() > timeout:
            if self.tdef.rtconfig['simulation mode']['simulate failure']:
                self.message_queue.put('NORMAL', self.identity + ' submitted')
                self.message_queue.put('CRITICAL', self.identity + ' failed')
            else:
                self.message_queue.put('NORMAL', self.identity + ' submitted')
                self.message_queue.put('NORMAL', self.identity + ' succeeded')
            return True
        else:
            return False

    def reject_if_failed(self, message):
        """Reject a message if in the failed state.

        Handle 'enable resurrection' mode.

        """
        if self.state.is_currently('failed'):
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

    def process_incoming_messages(self):
        """Handle incoming messages."""
        queue = self.message_queue.get_queue()
        while queue.qsize() > 0:
            try:
                self.process_incoming_message(queue.get(block=False))
            except Queue.Empty:
                break
            queue.task_done()

    def process_incoming_message(
            self, (priority, message), msg_was_polled=False):
        """Parse an incoming task message and update task state.

        Correctly handle late (out of order) message which would otherwise set
        the state backward in the natural order of events.

        """
        # TODO - formalize state ordering, for: 'if new_state < old_state'

        # Log incoming messages with '>' to distinguish non-message log entries
        self.log(
            self.LOGGING_LVL_OF.get(priority, INFO),
            '(current:' + self.state.get_status() + ')> ' + message)
        # always update the suite state summary for latest message
        self.summary['latest_message'] = message.replace(
            self.identity, "", 1).strip()
        flags.iflag = True

        if self.reject_if_failed(message):
            # Failed tasks do not send messages unless declared resurrectable
            return

        # Remove the prepended task ID.
        message = self.MESSAGE_SUFFIX_RE.sub('', message)
        content = message.replace(self.identity + ' ', '')

        # If the message matches a registered output, record it as completed.
        if self.outputs.exists(message):
            if not self.outputs.is_completed(message):
                flags.pflag = True
                self.outputs.set_completed(message)
                self._db_events_insert(
                    event="output completed", message=content)
            elif not msg_was_polled:
                # This output has already been reported complete. Not an error
                # condition - maybe the network was down for a bit. Ok for
                # polling as multiple polls *should* produce the same result.
                self.log(
                    WARNING,
                    "Unexpected output (already completed):\n  " + message)

        if msg_was_polled and not self.is_active():
            # Polling can take a few seconds or more, so it is
            # possible for a poll result to come in after a task
            # finishes normally (success or failure) - in which case
            # we should ignore the poll result.
            self.log(
                WARNING,
                "Ignoring late poll result: task is not active")
            return

        if priority == TaskMessage.WARNING:
            self.setup_event_handlers('warning', content, db_update=False)

        if self._get_events_conf('reset timer'):
            # Reset execution timer on incoming messages
            execution_timeout = self._get_events_conf('execution timeout')
            if execution_timeout:
                self.execution_timer_timeout = (
                    time.time() + execution_timeout
                )

        elif (content == TaskMessage.STARTED and
                self.state.is_currently(
                    'ready', 'submitted', 'submit-failed')):
            if self.job_vacated:
                self.job_vacated = False
                self.log(WARNING, "Vacated job restarted: " + message)
            # Received a 'task started' message
            flags.pflag = True
            self.set_status('running')
            self.started_time = time.time()  # TODO: use time from message
            self.summary['started_time'] = self.started_time
            self.summary['started_time_string'] = (
                get_time_string_from_unix_time(self.started_time))
            self.db_updates_map[self.TABLE_TASK_JOBS].append({
                "time_run": self.summary['started_time_string']})
            execution_timeout = self._get_events_conf('execution timeout')
            if execution_timeout:
                self.execution_timer_timeout = (
                    self.started_time + execution_timeout
                )
            else:
                self.execution_timer_timeout = None

            # submission was successful so reset submission try number
            self.sub_try_state.num = 0
            self.setup_event_handlers('started', 'job started')
            self.execution_poll_timer.set_timer()

        elif (content == TaskMessage.SUCCEEDED and
                self.state.is_currently(
                    'ready', 'submitted', 'submit-failed', 'running',
                    'failed')):
            # Received a 'task succeeded' message
            # (submit* states in case of very fast submission and execution)
            self.execution_timer_timeout = None
            self.hold_on_retry = False
            flags.pflag = True
            self.finished_time = time.time()
            self.summary['finished_time'] = self.finished_time
            self.summary['finished_time_string'] = (
                get_time_string_from_unix_time(self.finished_time))
            self.db_updates_map[self.TABLE_TASK_JOBS].append({
                "run_status": 0,
                "time_run_exit": self.summary['finished_time_string'],
            })
            # Update mean elapsed time only on task succeeded.
            self.tdef.update_mean_total_elapsed_time(
                self.started_time, self.finished_time)
            self.set_status('succeeded')
            self.setup_event_handlers("succeeded", "job succeeded")
            if not self.outputs.all_completed():
                msg = "Succeeded with unreported outputs:"
                for key in self.outputs.not_completed:
                    msg += "\n  " + key
                self.log(WARNING, msg)
                if msg_was_polled:
                    # Assume all outputs complete (e.g. poll at restart).
                    # TODO - just poll for outputs in the job status file.
                    self.log(WARNING, "Assuming ALL outputs completed.")
                    self.outputs.set_all_completed()
                else:
                    # A succeeded task MUST have submitted and started.
                    # TODO - just poll for outputs in the job status file?
                    for output in [self.identity + ' submitted',
                                   self.identity + ' started']:
                        if not self.outputs.is_completed(output):
                            msg = "Assuming output completed:  \n %s" % output
                            self.log(WARNING, msg)
                            self.outputs.set_completed(output)

        elif (content == TaskMessage.FAILED and
                self.state.is_currently(
                    'ready', 'submitted', 'submit-failed', 'running')):
            # (submit- states in case of very fast submission and execution).
            self.job_execution_failed()

        elif content.startswith(TaskMessage.FAIL_MESSAGE_PREFIX):
            # capture and record signals sent to task proxy
            self._db_events_insert(event="signaled", message=content)
            signal = content.replace(TaskMessage.FAIL_MESSAGE_PREFIX, "")
            self.db_updates_map[self.TABLE_TASK_JOBS].append(
                {"run_signal": signal})

        elif content.startswith(TaskMessage.VACATION_MESSAGE_PREFIX):
            flags.pflag = True
            self.set_status('submitted')
            self._db_events_insert(event="vacated", message=content)
            self.execution_timer_timeout = None
            # TODO - check summary item value compat with GUI:
            self.summary['started_time'] = None
            self.summary['started_time_string'] = None
            self.sub_try_state.num = 0
            self.job_vacated = True

        elif content == "submission failed":
            # This can arrive via a poll.
            outp = self.identity + ' submitted'
            if self.outputs.is_completed(outp):
                self.outputs.remove(outp)
            self.submission_timer_timeout = None
            self.job_submission_failed()

        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            self.log(DEBUG, '(current: %s) unhandled: %s' % (
                self.state.get_status(), content))

    def set_status(self, status):
        """Set, log and record task status."""
        if status != self.state.get_status():
            flags.iflag = True
            self.log(DEBUG, '(setting:' + status + ')')
            self.state.set_status(status)
            self.db_updates_map[self.TABLE_TASK_STATES].append({
                "time_updated": get_current_time_string(),
                "submit_num": self.submit_num,
                "try_num": self.run_try_state.num + 1,
                "status": status
            })

    def dump_state(self, handle):
        """Write state information to the state dump file."""
        handle.write(self.identity + ' : ' + self.state.dump() + '\n')

    def spawn(self, state):
        """Spawn the successor of this task proxy."""
        self.state.set_spawned()
        next_point = self.next_point()
        if next_point:
            return TaskProxy(self.tdef, next_point, state, self.stop_point)
        else:
            # next_point instance is out of the sequence bounds
            return None

    def ready_to_spawn(self):
        """Spawn on submission.

        Prevents uncontrolled spawning but allows successive instances to run
        in parallel.

        A task can only fail after first being submitted, therefore a failed
        task should spawn if it hasn't already. Resetting a waiting task to
        failed will result in it spawning.

        """
        if self.tdef.is_coldstart:
            self.state.set_spawned()
        return not self.state.has_spawned() and self.state.is_currently(
            'expired', 'submitted', 'running', 'succeeded', 'failed',
            'retrying')

    def done(self):
        """Return True if task has succeeded and spawned."""
        return (
            self.state.is_currently('succeeded') and self.state.has_spawned())

    def is_active(self):
        """Return True if task is in "submitted" or "running" state."""
        return self.state.is_currently('submitted', 'running')

    def get_state_summary(self):
        """Return a dict containing the state summary of this task proxy."""
        self.summary['state'] = self.state.get_status()
        self.summary['spawned'] = self.state.has_spawned()
        self.summary['mean total elapsed time'] = (
            self.tdef.mean_total_elapsed_time)
        return self.summary

    def not_fully_satisfied(self):
        """Return True if prerequisites are not fully satisfied."""
        return (not self.prerequisites_are_all_satisfied() or
                not self.suicide_prerequisites_are_all_satisfied())

    def satisfy_me(self, task_outputs):
        """Attempt to get my prerequisites satisfied."""
        for preqs in [self.prerequisites, self.suicide_prerequisites]:
            for preq in preqs:
                preq.satisfy_me(task_outputs)

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

    def _create_job_log_path(self, new_mode=False):
        """Return a new job log path on the suite host, in two parts.

        /part1/part2

        * part1: the top level job log directory on the suite host.
        * part2: the rest, which is also used on remote task hosts.

        The full local job log directory is created if necessary, and its
        parent symlinked to NN (submit number).

        """

        suite_job_log_dir = GLOBAL_CFG.get_derived_host_item(
            self.suite_name, "suite job log directory")

        the_rest_dir = os.path.join(
            str(self.point), self.tdef.name, "%02d" % int(self.submit_num))
        the_rest = os.path.join(the_rest_dir, "job")

        local_log_dir = os.path.join(suite_job_log_dir, the_rest_dir)

        if new_mode:
            try:
                rmtree(local_log_dir)
            except OSError:
                pass

        mkdir_p(local_log_dir)
        target = os.path.join(os.path.dirname(local_log_dir), "NN")
        try:
            os.unlink(target)
        except OSError:
            pass
        try:
            os.symlink(os.path.basename(local_log_dir), target)
        except OSError as exc:
            if not exc.filename:
                exc.filename = target
            raise exc
        return suite_job_log_dir, the_rest

    def _run_job_command(self, cmd_key, args, callback, stdin_file_paths=None):
        """Help for self.submit.

        Run a job command with the multiprocess pool.

        """
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

        # Queue the command for execution
        self.log(INFO, "job(%02d) initiate %s" % (self.submit_num, cmd_key))
        ctx = SuiteProcContext(
            cmd_key, cmd, stdin_file_paths=stdin_file_paths)
        return SuiteProcPool.get_inst().put_command(ctx, callback)

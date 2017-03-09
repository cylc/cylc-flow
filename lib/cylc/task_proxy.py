#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
from logging import (
    getLevelName, CRITICAL, ERROR, WARNING, INFO, DEBUG)
import os
from pipes import quote
import re
import time

from isodatetime.timezone import get_local_time_zone

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
from cylc.batch_sys_manager import BatchSysManager
from cylc.owner import USER
from cylc.suite_host import get_suite_host
from cylc.network.suite_broadcast_server import BroadcastServer
from cylc.rundb import CylcSuiteDAO
from cylc.task_id import TaskID
from cylc.task_message import TaskMessage
from parsec.util import pdeepcopy, poverride
from parsec.config import ItemNotFoundError
from cylc.task_action_timer import TaskActionTimer
from cylc.task_state import (
    TaskState, TASK_STATUSES_ACTIVE, TASK_STATUS_WAITING,
    TASK_STATUS_READY, TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING, TASK_STATUS_FAILED)
from cylc.task_outputs import (
    TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED)
from cylc.suite_logging import LOG


CustomTaskEventHandlerContext = namedtuple(
    "CustomTaskEventHandlerContext",
    ["key", "ctx_type", "cmd"])


TaskEventMailContext = namedtuple(
    "TaskEventMailContext",
    ["key", "ctx_type", "mail_from", "mail_to", "mail_smtp"])


TaskJobLogsRetrieveContext = namedtuple(
    "TaskJobLogsRetrieveContext",
    ["key", "ctx_type", "user_at_host", "max_size"])


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
    __slots__ = ["CUSTOM_EVENT_HANDLER", "EVENT_MAIL", "JOB_LOGS_RETRIEVE",
                 "KEY_EXECUTE", "KEY_SUBMIT", "NN",
                 "LOGGING_LVL_OF", "RE_MESSAGE_TIME", "TABLE_TASK_JOBS",
                 "TABLE_TASK_EVENTS", "TABLE_TASK_STATES", "POLLED_INDICATOR",
                 "tdef", "submit_num",
                 "point", "cleanup_cutoff", "identity", "has_spawned",
                 "point_as_seconds", "stop_point", "manual_trigger",
                 "is_manual_submit", "summary", "local_job_file_path",
                 "try_timers", "event_handler_try_timers", "db_inserts_map",
                 "db_updates_map", "suite_name", "task_host", "task_owner",
                 "job_vacated", "poll_timers", "events_conf",
                 "delayed_start", "expire_time", "state"]

    CUSTOM_EVENT_HANDLER = "event-handler"
    EVENT_MAIL = "event-mail"
    JOB_LOGS_RETRIEVE = "job-logs-retrieve"
    KEY_EXECUTE = "execution"
    KEY_EXECUTE_TIME_LIMIT = "execution_time_limit"
    KEY_SUBMIT = "submission"
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

    def __init__(
            self, tdef, start_point, status=TASK_STATUS_WAITING,
            hold_swap=None, has_spawned=False, stop_point=None,
            is_startup=False, validate_mode=False, submit_num=0,
            is_reload_or_restart=False, pre_reload_inst=None):
        self.tdef = tdef
        if submit_num is None:
            self.submit_num = 0
        else:
            self.submit_num = submit_num

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

        overrides = BroadcastServer.get_inst().get(self.identity)
        if overrides:
            rtconfig = pdeepcopy(self.tdef.rtconfig)
            poverride(rtconfig, overrides)
        else:
            rtconfig = self.tdef.rtconfig

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
            'description': rtconfig['description'],
            'title': rtconfig['title'],
            'label': str(self.point),
            'logfiles': [],
            'job_hosts': {},
            'execution_time_limit': None,
        }
        for lfile in rtconfig['extra log files']:
            self.summary['logfiles'].append(expandvars(lfile))

        self.local_job_file_path = None

        self.try_timers = {
            self.KEY_EXECUTE: TaskActionTimer(delays=[]),
            self.KEY_SUBMIT: TaskActionTimer(delays=[])}
        self.event_handler_try_timers = {}

        self.db_inserts_map = {
            self.TABLE_TASK_JOBS: [],
            self.TABLE_TASK_STATES: [],
            self.TABLE_TASK_EVENTS: [],
        }
        self.db_updates_map = {
            self.TABLE_TASK_JOBS: [],
            self.TABLE_TASK_STATES: [],
        }

        # In case task owner and host are needed by db_events_insert()
        # for pre-submission events, set their initial values as if
        # local (we can't know the correct host prior to this because
        # dynamic host selection could be used).
        self.task_host = 'localhost'
        self.task_owner = None

        self.job_vacated = False

        # An initial db state entry is created at task proxy init. On reloading
        # or restarting the suite, the task proxies already have this db entry.
        if (not validate_mode and not is_reload_or_restart and
                self.submit_num == 0):
            self.db_inserts_map[self.TABLE_TASK_STATES].append({
                "time_created": get_current_time_string(),
                "time_updated": get_current_time_string(),
                "status": status})

        if not validate_mode and self.submit_num > 0:
            self.db_updates_map[self.TABLE_TASK_STATES].append({
                "time_updated": get_current_time_string(),
                "status": status})

        self.events_conf = rtconfig['events']
        # configure retry delays before the first try
        if self.tdef.run_mode == 'live':
            # note that a *copy* of the retry delays list is needed
            # so that all instances of the same task don't pop off
            # the same deque
            self.try_timers[self.KEY_EXECUTE].delays = list(
                rtconfig['job']['execution retry delays'])
            self.try_timers[self.KEY_SUBMIT].delays = list(
                rtconfig['job']['submission retry delays'])
        self.poll_timers = {}
        for key in self.KEY_SUBMIT, self.KEY_EXECUTE:
            values = self.get_host_conf(
                key + ' polling intervals', skey='job')
            if values:
                self.poll_timers[key] = TaskActionTimer(delays=values)

        self.delayed_start = None
        self.expire_time = None

        self.state = TaskState(tdef, self.point, status, hold_swap)

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
            self.submit_num = pre_reload_inst.submit_num
            self.has_spawned = pre_reload_inst.has_spawned
            self.manual_trigger = pre_reload_inst.manual_trigger
            self.is_manual_submit = pre_reload_inst.is_manual_submit
            self.summary = pre_reload_inst.summary
            self.local_job_file_path = pre_reload_inst.local_job_file_path
            self.try_timers = pre_reload_inst.try_timers
            self.event_handler_try_timers = (
                pre_reload_inst.event_handler_try_timers)
            self.db_inserts_map = pre_reload_inst.db_inserts_map
            self.db_updates_map = pre_reload_inst.db_updates_map
            self.task_host = pre_reload_inst.task_host
            self.task_owner = pre_reload_inst.task_owner
            self.job_vacated = pre_reload_inst.job_vacated
            self.poll_timers = pre_reload_inst.poll_timers
            # Retain status of outputs.
            for msg, oid in pre_reload_inst.state.outputs.completed.items():
                self.state.outputs.completed[msg] = oid
                try:
                    del self.state.outputs.not_completed[msg]
                except KeyError:
                    pass

    def _get_events_conf(self, key, default=None):
        """Return an events setting from suite then global configuration."""
        for getter in [self.events_conf, GLOBAL_CFG.get()["task events"]]:
            try:
                value = getter.get(key)
                if value is not None:
                    return value
            except (ItemNotFoundError, KeyError):
                pass
        return default

    def get_host_conf(self, key, default=None, skey="remote"):
        """Return a host setting from suite then global configuration."""
        overrides = BroadcastServer.get_inst().get(self.identity)
        if skey in overrides and overrides[skey].get(key) is not None:
            return overrides[skey][key]
        elif self.tdef.rtconfig[skey].get(key) is not None:
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

    def db_events_insert(self, event="", message=""):
        """Record an event to the DB."""
        self.db_inserts_map[self.TABLE_TASK_EVENTS].append({
            "time": get_current_time_string(),
            "event": event,
            "message": message})

    def retry_delay_done(self):
        """Is retry delay done? Can I retry now?"""
        now = time.time()
        return (self.try_timers[self.KEY_EXECUTE].is_delay_done(now) or
                self.try_timers[self.KEY_SUBMIT].is_delay_done(now))

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
        return time.time() > self.delayed_start

    def _has_expired(self):
        """Is this task past its use-by date?"""
        if self.tdef.expiration_offset is None:
            return False
        if self.expire_time is None:
            self.expire_time = (
                self.get_point_as_seconds() +
                self.get_offset_as_seconds(self.tdef.expiration_offset))
        return time.time() > self.expire_time

    def setup_event_handlers(
            self, event, message, db_update=True, db_event=None, db_msg=None):
        """Set up event handlers."""
        # extra args for inconsistent use between events, logging, and db
        # updates
        db_event = db_event or event
        if db_update:
            self.db_events_insert(event=db_event, message=db_msg)
        if (self.tdef.run_mode in ['simulation', 'dummy', 'dummy-local'] and
            self.tdef.rtconfig[
                'simulation']['disable task event handlers']):
            return
        if self.tdef.run_mode != 'simulation':
            self.setup_job_logs_retrieval(event, message)
        self.setup_event_mail(event, message)
        self.setup_custom_event_handlers(event, message)

    def setup_job_logs_retrieval(self, event, _=None):
        """Set up remote job logs retrieval."""
        key2 = ((self.JOB_LOGS_RETRIEVE, event), self.submit_num)
        if self.task_owner:
            user_at_host = self.task_owner + "@" + self.task_host
        else:
            user_at_host = self.task_host
        # TODO - use string constants for event names.
        if (event not in ['failed', 'retry', 'succeeded'] or
                user_at_host in [USER + '@localhost', 'localhost'] or
                not self.get_host_conf("retrieve job logs") or
                key2 in self.event_handler_try_timers):
            return
        retry_delays = self.get_host_conf("retrieve job logs retry delays")
        if not retry_delays:
            retry_delays = [0]
        self.event_handler_try_timers[key2] = TaskActionTimer(
            TaskJobLogsRetrieveContext(
                self.JOB_LOGS_RETRIEVE,  # key
                self.JOB_LOGS_RETRIEVE,  # ctx_type
                user_at_host,
                self.get_host_conf("retrieve job logs max size"),  # max_size
            ),
            retry_delays)

    def setup_event_mail(self, event, _):
        """Event notification, by email."""
        key2 = ((self.EVENT_MAIL, event), self.submit_num)
        if (key2 in self.event_handler_try_timers or
                event not in self._get_events_conf("mail events", [])):
            return
        retry_delays = self._get_events_conf("mail retry delays")
        if not retry_delays:
            retry_delays = [0]
        self.event_handler_try_timers[key2] = TaskActionTimer(
            TaskEventMailContext(
                self.EVENT_MAIL,  # key
                self.EVENT_MAIL,  # ctx_type
                self._get_events_conf(  # mail_from
                    "mail from",
                    "notifications@" + get_suite_host(),
                ),
                self._get_events_conf("mail to", USER),  # mail_to
                self._get_events_conf("mail smtp"),  # mail_smtp
            ),
            retry_delays)

    def setup_custom_event_handlers(self, event, message, only_list=None):
        """Call custom event handlers."""
        handlers = self._get_events_conf(event + ' handler')
        if (handlers is None and
                event in self._get_events_conf('handler events', [])):
            handlers = self._get_events_conf('handlers')
        if handlers is None:
            return
        retry_delays = self._get_events_conf(
            'handler retry delays',
            self.get_host_conf("task event handler retry delays"))
        if not retry_delays:
            retry_delays = [0]
        for i, handler in enumerate(handlers):
            key1 = ("%s-%02d" % (self.CUSTOM_EVENT_HANDLER, i), event)
            if (key1, self.submit_num) in self.event_handler_try_timers or (
                    only_list and i not in only_list):
                continue
            cmd = handler % {
                "event": quote(event),
                "suite": quote(self.__class__.suite_name),
                "point": quote(str(self.point)),
                "name": quote(self.tdef.name),
                "submit_num": self.submit_num,
                "id": quote(self.identity),
                "task_url": quote(self.tdef.rtconfig['URL']),
                "suite_url": quote(self.__class__.suite_url),
                "message": quote(message),
            }
            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = "%s '%s' '%s' '%s' '%s'" % (
                    handler, event, self.__class__.suite_name,
                    self.identity, message)
            self.log(DEBUG, "Queueing %s handler: %s" % (event, cmd))
            self.event_handler_try_timers[(key1, self.submit_num)] = (
                TaskActionTimer(
                    CustomTaskEventHandlerContext(
                        key1,
                        self.CUSTOM_EVENT_HANDLER,
                        cmd,
                    ),
                    retry_delays))

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
        if self.try_timers[self.KEY_SUBMIT].next() is None:
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
            timeout_str = self.try_timers[self.KEY_SUBMIT].timeout_as_str()

            delay_msg = "submit-retrying in %s" % (
                self.try_timers[self.KEY_SUBMIT].delay_as_seconds())
            msg = "submission failed, %s (after %s)" % (delay_msg, timeout_str)
            self.log(INFO, "job(%02d) " % self.submit_num + msg)
            self.summary['latest_message'] = msg
            self.db_events_insert(
                event="submission failed", message=delay_msg)
            # TODO - is this insert redundant with setup_event_handlers?
            self.db_events_insert(
                event="submission failed",
                message="submit-retrying in " + str(
                    self.try_timers[self.KEY_SUBMIT].delay))
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
            self.summary['started_time'] = now
            self.summary['started_time_string'] = now_string
            self.state.set_state(TASK_STATUS_RUNNING)
            self.state.outputs.set_completed(TASK_OUTPUT_STARTED)
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
            try:
                self.state.submission_timer_timeout = (
                    self.summary['submitted_time'] +
                    float(self._get_events_conf('submission timeout')))
            except (TypeError, ValueError):
                self.state.submission_timer_timeout = None
            self._set_next_poll_time(self.KEY_SUBMIT)

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
        if self.try_timers[self.KEY_EXECUTE].next() is None:
            # No retry lined up: definitive failure.
            # Note the TASK_STATUS_FAILED output is only added if needed.
            flags.pflag = True
            self.state.set_execution_failed()
            self.setup_event_handlers("failed", 'job failed')
        else:
            # There is a retry lined up
            timeout_str = self.try_timers[self.KEY_EXECUTE].timeout_as_str()
            delay_msg = "retrying in %s" % (
                self.try_timers[self.KEY_EXECUTE].delay_as_seconds())
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
            self.try_timers[self.KEY_EXECUTE].timeout = None
            self.try_timers[self.KEY_SUBMIT].timeout = None

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
            timer = self.poll_timers[self.KEY_EXECUTE_TIME_LIMIT]
            if not timer.is_timeout_set():
                timer.next()
            if not timer.is_delay_done():
                # Don't poll
                return False
            if timer.next() is not None:
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

    def sim_job_fail(self):
        """Should this task instance simulate job failure?"""
        if (self.tdef.rtconfig['simulation']['fail try 1 only'] and
                self.try_timers[self.KEY_EXECUTE].num != 0):
            return False
        fail_pts = self.tdef.rtconfig['simulation']['fail cycle points']
        return fail_pts is None or self.point in fail_pts

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
        if self.state.outputs.exists(message):
            if not self.state.outputs.is_completed(message):
                flags.pflag = True
                self.state.outputs.set_completed(message)
                self.db_events_insert(
                    event="output completed", message=message)
            elif not is_polled:
                # This output has already been reported complete. Not an error
                # condition - maybe the network was down for a bit. Ok for
                # polling as multiple polls *should* produce the same result.
                self.log(WARNING, (
                    "Unexpected output (already completed):\n  %s" % message))

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
            self.state.set_state(TASK_STATUS_RUNNING)
            self.summary['started_time'] = float(
                get_unix_time_from_time_string(event_time))
            self.summary['started_time_string'] = event_time
            self.db_updates_map[self.TABLE_TASK_JOBS].append({
                "time_run": self.summary['started_time_string']})
            if self.summary['execution_time_limit']:
                execution_timeout = self.summary['execution_time_limit']
            else:
                execution_timeout = self._get_events_conf('execution timeout')
            try:
                self.state.execution_timer_timeout = (
                    self.summary['started_time'] + float(execution_timeout))
            except (TypeError, ValueError):
                self.state.execution_timer_timeout = None

            # submission was successful so reset submission try number
            self.try_timers[self.KEY_SUBMIT].num = 0
            self.setup_event_handlers('started', 'job started')
            self._set_next_poll_time(self.KEY_EXECUTE)

        elif (message == TASK_OUTPUT_SUCCEEDED and
                self.state.status in [
                    TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
                    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_RUNNING,
                    TASK_STATUS_FAILED]):
            # Received a 'task succeeded' message
            self.state.execution_timer_timeout = None
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
            warnings = self.state.set_execution_succeeded(is_polled)
            for warning in warnings:
                self.log(WARNING, warning)

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
            self.try_timers[self.KEY_SUBMIT].num = 0
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

            # TODO - custom outputs shouldn't drop through to here.
            self.log(DEBUG, '(current:%s) unhandled: %s' % (
                self.state.status, message))
            if priority in [CRITICAL, ERROR, WARNING, INFO, DEBUG]:
                priority = getLevelName(priority)
            self.db_events_insert(
                event=("message %s" % str(priority).lower()), message=message)

    def get_state_summary(self):
        """Return a dict containing the state summary of this task proxy."""
        self.summary['state'] = self.state.status
        self.summary['spawned'] = str(self.has_spawned)
        count = len(self.tdef.elapsed_times)
        if count:
            self.summary['mean_elapsed_time'] = (
                float(sum(self.tdef.elapsed_times)) / count)
        elif self.summary['execution_time_limit']:
            self.summary['mean_elapsed_time'] = \
                self.summary['execution_time_limit']
        else:
            self.summary['mean_elapsed_time'] = None

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

    def check_poll_ready(self, now=None):
        """Check if it is the next poll time."""
        return (
            self.state.status == TASK_STATUS_SUBMITTED and (
                self.check_submission_timeout(now) or
                self._check_poll_timer(self.KEY_SUBMIT, now)
            )
        ) or (
            self.state.status == TASK_STATUS_RUNNING and (
                self.check_execution_timeout(now) or
                self._check_poll_timer(self.KEY_EXECUTE, now)
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

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
from logging import WARNING, INFO, DEBUG
import os
from pipes import quote
import time

from isodatetime.timezone import get_local_time_zone
from parsec.config import ItemNotFoundError
from parsec.util import pdeepcopy, poverride

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.cycling.iso8601
from cylc.envvar import expandvars
from cylc.network.suite_broadcast_server import BroadcastServer
from cylc.owner import USER
from cylc.rundb import CylcSuiteDAO
from cylc.suite_host import get_suite_host
from cylc.suite_logging import LOG
from cylc.task_id import TaskID
from cylc.task_action_timer import TaskActionTimer
from cylc.task_state import (
    TaskState, TASK_STATUSES_ACTIVE, TASK_STATUS_WAITING,
    TASK_STATUS_SUBMITTED, TASK_STATUS_RUNNING)
from cylc.wallclock import (
    get_current_time_string, get_seconds_as_interval_string,
    get_unix_time_from_time_string)


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
                 "TABLE_TASK_JOBS",
                 "TABLE_TASK_EVENTS", "TABLE_TASK_STATES",
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

    TABLE_TASK_JOBS = CylcSuiteDAO.TABLE_TASK_JOBS
    TABLE_TASK_EVENTS = CylcSuiteDAO.TABLE_TASK_EVENTS
    TABLE_TASK_STATES = CylcSuiteDAO.TABLE_TASK_STATES

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

    def set_event_time(self, event_key, time_str=None):
        """Set event time in self.summary

        Set values of both event_key + "_time" and event_key + "_time_string".
        """
        if time_str is None:
            self.summary[event_key + '_time'] = None
        else:
            self.summary[event_key + '_time'] = float(
                get_unix_time_from_time_string(time_str))
        self.summary[event_key + '_time_string'] = time_str

    def _check_poll_timer(self, key, now=None):
        """Set the next execution/submission poll time."""
        timer = self.poll_timers.get(key)
        if timer is not None and timer.is_delay_done(now):
            self.set_next_poll_time(key)
            return True
        else:
            return False

    def set_next_poll_time(self, key):
        """Set the next execution/submission poll time."""
        timer = self.poll_timers.get(key)
        if timer is not None:
            if timer.num is None:
                timer.num = 0
            delay = timer.next(no_exhaust=True)
            if delay is not None:
                self.log(INFO, 'next job poll in %s (after %s)' % (
                    timer.delay_as_seconds(), timer.timeout_as_str()))

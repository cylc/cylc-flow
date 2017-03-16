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

from logging import WARNING, INFO

from isodatetime.timezone import get_local_time_zone
from parsec.config import ItemNotFoundError
from parsec.util import pdeepcopy, poverride

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.cycling.iso8601
from cylc.envvar import expandvars
from cylc.network.suite_broadcast_server import BroadcastServer
from cylc.suite_logging import LOG
from cylc.task_id import TaskID
from cylc.task_action_timer import TaskActionTimer
from cylc.task_state import (
    TaskState, TASK_STATUSES_ACTIVE, TASK_STATUS_WAITING)
from cylc.wallclock import get_unix_time_from_time_string


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
    __slots__ = ["KEY_EXECUTE", "KEY_SUBMIT",
                 "tdef", "submit_num",
                 "point", "cleanup_cutoff", "identity", "has_spawned",
                 "point_as_seconds", "stop_point", "manual_trigger",
                 "is_manual_submit", "summary", "local_job_file_path",
                 "try_timers", "task_host", "task_owner",
                 "job_vacated", "poll_timers", "events_conf",
                 "delayed_start", "expire_time", "state"]

    KEY_EXECUTE = "execution"
    KEY_SUBMIT = "submission"

    def __init__(
            self, tdef, start_point, status=TASK_STATUS_WAITING,
            hold_swap=None, has_spawned=False, stop_point=None,
            is_startup=False, submit_num=0, pre_reload_inst=None):
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

        self.task_host = 'localhost'
        self.task_owner = None

        self.job_vacated = False

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

        if pre_reload_inst is not None:
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

    def ready_to_run(self, now):
        """Am I in a pre-run state but ready to run?

        Queued tasks are not counted as they've already been deemed ready.

        """
        retry_delay_done = (
            self.try_timers[self.KEY_EXECUTE].is_delay_done(now) or
            self.try_timers[self.KEY_SUBMIT].is_delay_done(now))
        return self.state.is_ready_to_run(
            retry_delay_done, self.start_time_reached(now))

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

    def start_time_reached(self, now):
        """Has this task reached its clock trigger time?"""
        if self.tdef.clocktrigger_offset is None:
            return True
        if self.delayed_start is None:
            self.delayed_start = (
                self.get_point_as_seconds() +
                self.get_offset_as_seconds(self.tdef.clocktrigger_offset))

    def reset_manual_trigger(self):
        """This is called immediately after manual trigger flag used."""
        if self.manual_trigger:
            self.manual_trigger = False
            self.is_manual_submit = True
            # unset any retry delay timers
            self.try_timers[self.KEY_EXECUTE].timeout = None
            self.try_timers[self.KEY_SUBMIT].timeout = None

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

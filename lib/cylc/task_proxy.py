#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

from isodatetime.timezone import get_local_time_zone

import cylc.cycling.iso8601
from cylc.exceptions import TaskProxySequenceBoundsError
from cylc.task_id import TaskID
from cylc.task_state import (
    TaskState, TASK_STATUS_WAITING, TASK_STATUS_RETRYING)
from cylc.wallclock import get_unix_time_from_time_string as str2time


class TaskProxy(object):
    """Represent an instance of a cycling task in a running suite.

    Attributes:
        .cleanup_cutoff (cylc.cycling.PointBase):
            Cycle point beyond which this task can be removed from the pool.
        .clock_trigger_time (float):
            Clock trigger time in seconds since epoch.
        .expire_time (float):
            Time in seconds since epoch when this task is considered expired.
        .has_spawned (boolean):
            Has this task spawned its successor in the sequence?
        .identity (str):
            Task ID in NAME.POINT syntax.
        .is_late (boolean):
            Is the task late?
        .is_manual_submit (boolean):
            Is the latest job submission due to a manual trigger?
        .job_vacated (boolean):
            Is the latest job pre-empted (or vacated)?
        .local_job_file_path (str):
            Path on suite host to the latest job script for running the task.
        .late_time (float):
            Time in seconds since epoch, beyond which the task is considered
            late if it is never active.
        .manual_trigger (boolean):
            Has this task received a manual trigger command? This flag is reset
            on trigger.
        .non_unique_events (dict):
            Count non-unique events (e.g. critical, warning, custom).
        .point (cylc.cycling.PointBase):
            Cycle point of the task.
        .point_as_seconds (int):
            Cycle point as seconds since epoch.
        .poll_timer (cylc.task_action_timer.TaskActionTimer):
            Schedule for polling submitted or running jobs.
        .reload_successor (cylc.task_proxy.TaskProxy):
            The task proxy object that replaces the current instance on reload.
            This attribute provides a useful link to the latest replacement
            instance while the current object may still be referenced by a job
            manipulation command.
        .stop_point (cylc.cycling.PointBase):
            Do not spawn successor beyond this point.
        .submit_num (int):
            Number of times the task has attempted job submission.
        .summary (dict):
            batch_sys_name (str):
                Name of batch system where latest job is submitted.
            description (str):
                Same as the .tdef.rtconfig['meta']['description'] attribute.
            execution_time_limit (float):
                Execution time limit of latest job.
            finished_time (float):
                Latest job exit time.
            finished_time_string (str):
                Latest job exit time as string.
            job_hosts (dict):
                Jobs' owner@host by submit number.
            label (str):
                The .point attribute as string.
            latest_message (str):
                Latest job or event message.
            logfiles (list):
                List of names of (extra) known job log files.
            name (str):
                Same as the .tdef.name attribute.
            started_time (float):
                Latest job execution start time.
            started_time_string (str):
                Latest job execution start time as string.
            submit_method_id (str):
                Latest ID of job in batch system.
            submit_num (int):
                Same as the .submit_num attribute.
            submitted_time (float):
                Latest job submission time.
            submitted_time_string (str):
                Latest job submission time as string.
            title (str):
                Same as the .tdef.rtconfig['meta']['title'] attribute.
        .state (cylc.task_state.TaskState):
            Object representing the state of this task.
        .task_host (str)
            Name of host where latest job is submitted.
        .task_owner (str)
            Name of user (at task_host) where latest job is submitted.
        .tdef (cylc.taskdef.TaskDef):
            The definition object of this task.
        .timeout (float):
            Timeout value in seconds since epoch for latest job
            submission/execution.
        .try_timers (dict)
            Retry schedules as cylc.task_action_timer.TaskActionTimer objects.

    Arguments:
        tdef (cylc.taskdef.TaskDef):
            The definition object of this task.
        start_point (cylc.cycling.PointBase):
            Start point to calculate the task's cycle point on start up or the
            cycle point for subsequent tasks.
        status (str):
            Task state string.
        hold_swap (str):
            Original task state string, if task is held.
        has_spawned (boolean):
            Has this task spawned its successor in the sequence.
        stop_point (cylc.cycling.PointBase):
            Do not spawn successor beyond this point.
        is_startup (boolean):
            Is this on start up?
        submit_num (int):
            Number of times the task has attempted job submission.
        late_time (float):
            Time in seconds since epoch, beyond which the task is considered
            late if it is never active.
    """

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = [
        'cleanup_cutoff',
        'clock_trigger_time',
        'expire_time',
        'has_spawned',
        'identity',
        'is_late',
        'is_manual_submit',
        'job_vacated',
        'late_time',
        'local_job_file_path',
        'manual_trigger',
        'non_unique_events',
        'point',
        'point_as_seconds',
        'poll_timer',
        'reload_successor',
        'submit_num',
        'tdef',
        'state',
        'stop_point',
        'summary',
        'task_host',
        'task_owner',
        'timeout',
        'try_timers',
    ]

    def __init__(
            self, tdef, start_point, status=TASK_STATUS_WAITING,
            hold_swap=None, has_spawned=False, stop_point=None,
            is_startup=False, submit_num=0, is_late=False):
        self.tdef = tdef
        if submit_num is None:
            submit_num = 0
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
            self.late_time = None
        else:
            self.point = start_point
        self.cleanup_cutoff = self.tdef.get_cleanup_cutoff_point(self.point)
        self.identity = TaskID.get(self.tdef.name, self.point)

        self.has_spawned = has_spawned
        self.reload_successor = None
        self.point_as_seconds = None

        # Manually inserted tasks may have a final cycle point set.
        self.stop_point = stop_point

        self.manual_trigger = False
        self.is_manual_submit = False
        self.summary = {
            'latest_message': '',
            'submitted_time': None,
            'submitted_time_string': None,
            'started_time': None,
            'started_time_string': None,
            'finished_time': None,
            'finished_time_string': None,
            'logfiles': [],
            'job_hosts': {},
            'execution_time_limit': None,
            'batch_sys_name': None,
            'submit_method_id': None
        }

        self.local_job_file_path = None

        self.task_host = 'localhost'
        self.task_owner = None

        self.job_vacated = False
        self.poll_timer = None
        self.timeout = None
        self.try_timers = {}
        # Use dict here for Python 2.6 compat.
        # Should use collections.Counter in Python 2.7+
        self.non_unique_events = {}

        self.clock_trigger_time = None
        self.expire_time = None
        self.late_time = None
        self.is_late = is_late

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

    def __str__(self):
        """Stringify using "self.identity"."""
        return self.identity

    def copy_to_reload_successor(self, reload_successor):
        """Copy attributes to successor on reload of this task proxy."""
        self.reload_successor = reload_successor
        reload_successor.submit_num = self.submit_num
        reload_successor.has_spawned = self.has_spawned
        reload_successor.manual_trigger = self.manual_trigger
        reload_successor.is_manual_submit = self.is_manual_submit
        reload_successor.summary = self.summary
        reload_successor.local_job_file_path = self.local_job_file_path
        reload_successor.try_timers = self.try_timers
        reload_successor.task_host = self.task_host
        reload_successor.task_owner = self.task_owner
        reload_successor.job_vacated = self.job_vacated
        reload_successor.poll_timer = self.poll_timer
        reload_successor.timeout = self.timeout
        reload_successor.state.outputs = self.state.outputs
        reload_successor.state.is_updated = self.state.is_updated

    @staticmethod
    def get_offset_as_seconds(offset):
        """Return an ISO interval as seconds."""
        iso_offset = cylc.cycling.iso8601.interval_parse(str(offset))
        return int(iso_offset.get_seconds())

    def get_late_time(self):
        """Compute and store late time as seconds since epoch."""
        if self.late_time is None:
            if self.tdef.rtconfig['events']['late offset']:
                self.late_time = (
                    self.get_point_as_seconds() +
                    self.tdef.rtconfig['events']['late offset'])
            else:
                # Not used, but allow skip of the above "is None" test
                self.late_time = 0
        return self.late_time

    def get_point_as_seconds(self):
        """Compute and store my cycle point as seconds since epoch."""
        if self.point_as_seconds is None:
            iso_timepoint = cylc.cycling.iso8601.point_parse(str(self.point))
            self.point_as_seconds = int(iso_timepoint.get(
                'seconds_since_unix_epoch'))
            if iso_timepoint.time_zone.unknown:
                utc_offset_hours, utc_offset_minutes = (
                    get_local_time_zone())
                utc_offset_in_seconds = (
                    3600 * utc_offset_hours + 60 * utc_offset_minutes)
                self.point_as_seconds += utc_offset_in_seconds
        return self.point_as_seconds

    def get_state_summary(self):
        """Return a dict containing the state summary of this task proxy."""
        ret = self.summary.copy()
        ret['name'] = self.tdef.name
        ret['description'] = self.tdef.rtconfig['meta']['description']
        ret['title'] = self.tdef.rtconfig['meta']['title']
        ret['label'] = str(self.point)
        ret['submit_num'] = self.submit_num
        ret['state'] = self.state.status
        ret['spawned'] = str(self.has_spawned)
        ntimes = len(self.tdef.elapsed_times)
        if ntimes:
            ret['mean_elapsed_time'] = (
                float(sum(self.tdef.elapsed_times)) / ntimes)
        elif ret['execution_time_limit']:
            ret['mean_elapsed_time'] = float(
                ret['execution_time_limit'])
        else:
            ret['mean_elapsed_time'] = None
        return ret

    def get_try_num(self):
        """Return the number of automatic tries (try number)."""
        try:
            return self.try_timers[TASK_STATUS_RETRYING].num + 1
        except (AttributeError, KeyError):
            return 0

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

    def is_ready(self, now):
        """Am I in a pre-run state but ready to run?

        Queued tasks are not counted as they've already been deemed ready.

        """
        if self.manual_trigger:
            return True
        waiting_retry = self.is_waiting_retry(now)
        if waiting_retry is not None:
            return not waiting_retry
        if self.state.status != TASK_STATUS_WAITING:
            return False
        return not (self.is_waiting_clock(now) or self.is_waiting_prereqs())

    def reset_manual_trigger(self):
        """This is called immediately after manual trigger flag used."""
        if self.manual_trigger:
            self.manual_trigger = False
            self.is_manual_submit = True
            # unset any retry delay timers
            for timer in self.try_timers.values():
                timer.timeout = None

    def set_summary_message(self, message):
        """Set `.summary['latest_message']` if necessary.

        Set `.state.is_updated` to `True` if message is updated.
        """
        if self.summary['latest_message'] != message:
            self.summary['latest_message'] = message
            self.state.is_updated = True

    def set_summary_time(self, event_key, time_str=None):
        """Set an event time in self.summary

        Set values of both event_key + "_time" and event_key + "_time_string".
        """
        if time_str is None:
            self.summary[event_key + '_time'] = None
        else:
            self.summary[event_key + '_time'] = float(str2time(time_str))
        self.summary[event_key + '_time_string'] = time_str

    def is_waiting_clock(self, now):
        """Is this task waiting for its clock trigger time?"""
        if self.tdef.clocktrigger_offset is None:
            return None
        if self.clock_trigger_time is None:
            self.clock_trigger_time = (
                self.get_point_as_seconds() +
                self.get_offset_as_seconds(self.tdef.clocktrigger_offset))
        return self.clock_trigger_time > now

    def is_waiting_prereqs(self):
        """Is this task waiting for its prerequisites?"""
        return (
            any(not pre.is_satisfied() for pre in self.state.prerequisites)
            or any(not tri for tri in self.state.external_triggers.values())
            or not self.state.xtriggers_all_satisfied()
        )

    def is_waiting_retry(self, now):
        """Is this task waiting for its latest (submission) retry delay time?

        Return True if waiting for next retry delay time, False if not.
        Return None if no retry lined up.
        """
        try:
            return not self.try_timers[self.state.status].is_delay_done(now)
        except KeyError:
            return None

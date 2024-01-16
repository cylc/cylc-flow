# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

"""Provide a class to represent a task proxy in a running workflow."""

from collections import Counter
from copy import copy
from fnmatch import fnmatchcase
from time import time
from typing import (
    Any,
    Callable,
    Counter as TypingCounter,
    Dict,
    List,
    Iterable,
    Optional,
    Set,
    TYPE_CHECKING,
    Tuple,
)

from metomi.isodatetime.timezone import get_local_time_zone

from cylc.flow import LOG
from cylc.flow.flow_mgr import stringify_flow_nums
from cylc.flow.id import Tokens
from cylc.flow.platforms import get_platform
from cylc.flow.task_action_timer import TimerFlags
from cylc.flow.task_state import (
    TaskState,
    TASK_STATUS_WAITING,
    TASK_STATUS_EXPIRED
)
from cylc.flow.taskdef import generate_graph_children
from cylc.flow.wallclock import get_unix_time_from_time_string as str2time
from cylc.flow.cycling.iso8601 import (
    point_parse,
    interval_parse,
    ISO8601Interval
)

if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase
    from cylc.flow.task_action_timer import TaskActionTimer
    from cylc.flow.taskdef import TaskDef


class TaskProxy:
    """Represent an instance of a cycling task in a running workflow.

    Attributes:
        .clock_trigger_times:
            Memoization of clock trigger times (Used for wall_clock xtrigger):
            {offset string: seconds from epoch}
        .expire_time:
            Time in seconds since epoch when this task is considered expired.
        .identity:
            Task ID in POINT/NAME syntax.
        .tokens:
            Task ID tokens.
        .is_late:
            Is the task late?
        .is_manual_submit:
            Is the latest job submission due to a manual trigger?
        .job_vacated:
            Is the latest job pre-empted (or vacated)?
        .jobs:
            A list of job ids associated with the task proxy.
        .local_job_file_path:
            Path on workflow host to the latest job script for the task.
        .late_time:
            Time in seconds since epoch, beyond which the task is considered
            late if it is never active.
        .non_unique_events (collections.Counter):
            Count non-unique events (e.g. critical, warning, custom).
        .point:
            Cycle point of the task.
        .point_as_seconds:
            Cycle point as seconds since epoch.
        .poll_timer:
            Schedule for polling submitted or running jobs.
        .reload_successor:
            The task proxy object that replaces the current instance on reload.
            This attribute provides a useful link to the latest replacement
            instance while the current object may still be referenced by a job
            manipulation command.
        .submit_num:
            Number of times the task has attempted job submission.
        .summary (dict):
            job_runner_name (str):
                Name of job runner where latest job is submitted.
            description (str):
                Same as the .tdef.rtconfig['meta']['description'] attribute.
            execution_time_limit (float):
                Execution time limit of latest job.
            finished_time (float):
                Latest job exit time.
            finished_time_string (str):
                Latest job exit time as string.
            platforms_used (dict):
                Jobs' platform by submit number.
            label (str):
                The .point attribute as string.
            name (str):
                Same as the .tdef.name attribute.
            started_time (float):
                Latest job execution start time.
            started_time_string (str):
                Latest job execution start time as string.
            submit_method_id (str):
                Latest ID of job in job runner.
            submit_num (int):
                Same as the .submit_num attribute.
            submitted_time (float):
                Latest job submission time.
            submitted_time_string (str):
                Latest job submission time as string.
            title (str):
                Same as the .tdef.rtconfig['meta']['title'] attribute.
        .state:
            Object representing the state of this task.
        .platform:
            Dict containing info for platform where latest job is submitted.
        .tdef:
            The definition object of this task.
        .timeout:
            Timeout value in seconds since epoch for latest job
            submission/execution.
        .try_timers:
            Retry schedules as cylc.flow.task_action_timer.TaskActionTimer
            objects.
        .graph_children (dict)
            graph children: {msg: [(name, point), ...]}
        .flow_nums:
            flows I belong to
         flow_wait:
            wait for flow merge before spawning children
        .waiting_on_job_prep:
            True whilst task is awaiting job prep, reset to False once the
            preparation has completed.
        .transient:
            This is a transient proxy - not to be added to the task pool, but
            used e.g. to spawn children, or to get task-specific infomation.

    Args:
        tdef: The definition object of this task.
        start_point: Start point to calculate the task's cycle point on
            start-up or the cycle point for subsequent tasks.
        flow_nums: Which flows this task belongs to.
        status: Task state string.
        is_held: True if the task is held, else False.
        submit_num: Number of times the task has attempted job submission.
        is_late: Is the task late?
        data_mode: Reduced store reference data.
    """

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = [
        'clock_trigger_times',
        'expire_time',
        'identity',
        'is_late',
        'is_manual_submit',
        'job_vacated',
        'jobs',
        'late_time',
        'local_job_file_path',
        'non_unique_events',
        'point',
        'point_as_seconds',
        'poll_timer',
        'reload_successor',
        'submit_num',
        'tdef',
        'state',
        'summary',
        'flow_nums',
        'flow_wait',
        'graph_children',
        'platform',
        'timeout',
        'tokens',
        'try_timers',
        'waiting_on_job_prep',
        'transient'
    ]

    def __init__(
        self,
        scheduler_tokens: 'Tokens',
        tdef: 'TaskDef',
        start_point: 'PointBase',
        flow_nums: Optional[Set[int]] = None,
        status: str = TASK_STATUS_WAITING,
        is_held: bool = False,
        submit_num: int = 0,
        is_late: bool = False,
        is_manual_submit: bool = False,
        flow_wait: bool = False,
        data_mode: bool = False,
        transient: bool = False
    ) -> None:

        self.tdef = tdef
        if submit_num is None:
            submit_num = 0
        self.submit_num = submit_num
        self.jobs: List[dict] = []
        if flow_nums is None:
            self.flow_nums = set()
        else:
            # (don't share flow_nums ref with parent task)
            self.flow_nums = copy(flow_nums)
        self.flow_wait = flow_wait
        self.point = start_point
        self.tokens = scheduler_tokens.duplicate(
            cycle=str(self.point),
            task=self.tdef.name,
        )
        self.identity = self.tokens.relative_id
        self.reload_successor: Optional['TaskProxy'] = None
        self.point_as_seconds: Optional[int] = None

        self.is_manual_submit = is_manual_submit
        self.summary: Dict[str, Any] = {
            'submitted_time': None,
            'submitted_time_string': None,
            'started_time': None,
            'started_time_string': None,
            'finished_time': None,
            'finished_time_string': None,
            'platforms_used': {},
            'execution_time_limit': None,
            'job_runner_name': None,
            'submit_method_id': None,
            'flow_nums': set(),
            'flow_wait': self.flow_wait
        }

        self.local_job_file_path: Optional[str] = None

        if data_mode:
            self.platform = {}
        else:
            self.platform = get_platform()

        self.transient = transient

        self.job_vacated = False
        self.poll_timer: Optional['TaskActionTimer'] = None
        self.timeout: Optional[float] = None
        self.try_timers: Dict[str, 'TaskActionTimer'] = {}
        self.non_unique_events: TypingCounter[str] = Counter()

        self.clock_trigger_times: Dict[str, int] = {}
        self.expire_time: Optional[float] = None
        self.late_time: Optional[float] = None
        self.is_late = is_late
        self.waiting_on_job_prep = False

        self.state = TaskState(tdef, self.point, status, is_held)

        # Determine graph children of this task (for spawning).
        if data_mode:
            self.graph_children = {}
        else:
            self.graph_children = generate_graph_children(tdef, self.point)

        if self.tdef.expiration_offset is not None:
            self.expire_time = (
                self.get_point_as_seconds() +
                self.get_offset_as_seconds(
                    self.tdef.expiration_offset
                )
            )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.tokens}'>"

    def __str__(self) -> str:
        """Stringify with tokens, state, submit_num, and flow_nums.

        Format: "<point>/<name>/<job>{<flows>}:status".
        """
        return (
            f"{self.identity}/{self.submit_num:02d}"
            f"{stringify_flow_nums(self.flow_nums)}:{self.state}"
        )

    def copy_to_reload_successor(self, reload_successor, check_output):
        """Copy attributes to successor on reload of this task proxy."""
        self.reload_successor = reload_successor
        reload_successor.submit_num = self.submit_num
        reload_successor.flow_wait = self.flow_wait
        reload_successor.is_manual_submit = self.is_manual_submit
        reload_successor.summary = self.summary
        reload_successor.local_job_file_path = self.local_job_file_path
        reload_successor.try_timers = self.try_timers
        reload_successor.platform = self.platform
        reload_successor.job_vacated = self.job_vacated
        reload_successor.poll_timer = self.poll_timer
        reload_successor.timeout = self.timeout
        reload_successor.state.outputs = self.state.outputs
        reload_successor.state.is_held = self.state.is_held
        reload_successor.state.is_runahead = self.state.is_runahead
        reload_successor.state.is_updated = self.state.is_updated

        # Prerequisites: the graph might have changed before reload, so
        # we need to use the new prerequisites but update them with the
        # pre-reload state of prerequisites that still exist post-reload.

        # Get all prereq states, e.g. {('1', 'c', 'succeeded'): False, ...}
        pre_reload = {
            k: v
            for pre in self.state.prerequisites
            for (k, v) in pre.satisfied.items()
        }
        # Use them to update the new prerequisites.
        # - unchanged prerequisites will keep their pre-reload state.
        # - removed prerequisites will not be carried over
        # - added prerequisites will be recorded as unsatisfied
        #   NOTE: even if the corresponding output was completed pre-reload!
        for pre in reload_successor.state.prerequisites:
            for k in pre.satisfied.keys():
                try:
                    pre.satisfied[k] = pre_reload[k]
                except KeyError:
                    # Look through task outputs to see if is has been
                    # satisfied
                    pre.satisfied[k] = check_output(
                        *k,
                        self.flow_nums,
                    )

        reload_successor.state.xtriggers.update({
            # copy across any special "_cylc" xtriggers which were added
            # dynamically at runtime (i.e. execution retry xtriggers)
            key: value
            for key, value in self.state.xtriggers.items()
            if key.startswith('_cylc')
        })
        reload_successor.jobs = self.jobs

    @staticmethod
    def get_offset_as_seconds(offset):
        """Return an ISO interval as seconds."""
        iso_offset = interval_parse(str(offset))
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
            iso_timepoint = point_parse(str(self.point))
            self.point_as_seconds = int(iso_timepoint.seconds_since_unix_epoch)
            if iso_timepoint.time_zone.unknown:
                utc_offset_hours, utc_offset_minutes = (
                    get_local_time_zone())
                utc_offset_in_seconds = (
                    3600 * utc_offset_hours + 60 * utc_offset_minutes)
                self.point_as_seconds += utc_offset_in_seconds
        return self.point_as_seconds

    def get_clock_trigger_time(
        self,
        point: 'PointBase', offset_str: Optional[str] = None
    ) -> int:
        """Compute, cache and return trigger time relative to cycle point.

        Args:
            point: Task's cycle point.
            offset_str: ISO8601 interval string, e.g. "PT2M".
                Can be None for zero offset.
        Returns:
            Absolute trigger time in seconds since Unix epoch.

        """
        offset_str = offset_str if offset_str else 'P0Y'
        if offset_str not in self.clock_trigger_times:
            if offset_str == 'P0Y':
                trigger_time = point
            else:
                trigger_time = point + ISO8601Interval(offset_str)

            offset = int(
                point_parse(str(trigger_time)).seconds_since_unix_epoch)
            self.clock_trigger_times[offset_str] = offset
        return self.clock_trigger_times[offset_str]

    def get_try_num(self):
        """Return the number of automatic tries (try number)."""
        try:
            return self.try_timers[TimerFlags.EXECUTION_RETRY].num + 1
        except (AttributeError, KeyError):
            return 0

    def next_point(self):
        """Return the next cycle point."""
        return self.tdef.next_point(self.point)

    def is_ready_to_run(self) -> Tuple[bool, ...]:
        """Is this task ready to run?

        Takes account of all dependence: on other tasks, xtriggers, and
        old-style ext-triggers. Or, manual triggering.

        """
        if self.is_manual_submit:
            # Manually triggered, ignore unsatisfied prerequisites.
            return (True,)
        if self.state.is_held:
            # A held task is not ready to run.
            return (False,)
        if self.state.status in self.try_timers:
            # A try timer is still active.
            return (self.try_timers[self.state.status].is_delay_done(),)
        return (
            self.state(TASK_STATUS_WAITING),
            self.is_waiting_prereqs_done()
        )

    def set_summary_time(self, event_key, time_str=None):
        """Set an event time in self.summary

        Set values of both event_key + "_time" and event_key + "_time_string".
        """
        if time_str is None:
            self.summary[event_key + '_time'] = None
        else:
            self.summary[event_key + '_time'] = float(str2time(time_str))
        self.summary[event_key + '_time_string'] = time_str

    def is_task_prereqs_not_done(self):
        """Are some task prerequisites not satisfied?"""
        return (not all(pre.is_satisfied()
                for pre in self.state.prerequisites))

    def is_waiting_prereqs_done(self):
        """Are ALL prerequisites satisfied?"""
        return (
            all(pre.is_satisfied() for pre in self.state.prerequisites)
            and self.state.external_triggers_all_satisfied()
            and self.state.xtriggers_all_satisfied()
        )

    def reset_try_timers(self):
        # unset any retry delay timers
        for timer in self.try_timers.values():
            timer.timeout = None

    def status_match(self, status: Optional[str]) -> bool:
        """Return whether a string matches the task's status.

        None/an empty string is treated as a match.
        """
        return (not status) or self.state.status == status

    def name_match(
        self,
        value: str,
        match_func: Callable[[Any, Any], bool] = fnmatchcase
    ) -> bool:
        """Return whether a string/pattern matches the task's name or any of
        its parent family names."""
        return match_func(self.tdef.name, value) or any(
            match_func(ns, value) for ns in self.tdef.namespace_hierarchy
        )

    def merge_flows(self, flow_nums: Set) -> None:
        """Merge another set of flow_nums with mine."""
        self.flow_nums.update(flow_nums)
        LOG.info(
            f"[{self}] merged in flow(s) "
            f"{','.join(str(f) for f in flow_nums)}"
        )

    def state_reset(
        self, status=None, is_held=None, is_queued=None, is_runahead=None,
        silent=False
    ) -> bool:
        """Set new state and log the change. Return whether it changed."""
        before = str(self)
        if status == TASK_STATUS_EXPIRED:
            is_queued = False
        if self.state.reset(status, is_held, is_queued, is_runahead):
            if not silent and not self.transient:
                LOG.info(f"[{before}] => {self.state}")
            return True
        return False

    def satisfy_me(self, outputs: Iterable[str]) -> None:
        """Try to satisfy my prerequisites with given outputs.

        The output strings are of the form "cycle/task:message"
        Log a warning for outputs that I don't depend on.

        """
        tokens = [Tokens(p, relative=True) for p in outputs]
        used = self.state.satisfy_me(tokens)
        for output in set(outputs) - used:
            LOG.warning(
                f"{self.identity} does not depend on {output}"
            )

    def clock_expire(self) -> bool:
        """Return True if clock expire time is up, else False."""
        if (
            self.expire_time is None  # expiry not configured
            or self.state(TASK_STATUS_EXPIRED)  # already expired
            or time() < self.expire_time  # not time yet
        ):
            return False
        return True

    def is_complete(self) -> bool:
        """Return True if complete or expired, else False."""
        return (
            self.state(TASK_STATUS_EXPIRED)
            or not self.state.outputs.is_incomplete()
        )

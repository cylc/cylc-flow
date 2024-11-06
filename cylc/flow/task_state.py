# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.

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

"""Task state related logic."""


from typing import (
    TYPE_CHECKING,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
)

from cylc.flow.prerequisite import Prerequisite
from cylc.flow.task_outputs import (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_SUCCEEDED,
    TaskOutputs,
)
from cylc.flow.wallclock import get_current_time_string


if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase
    from cylc.flow.id import Tokens
    from cylc.flow.prerequisite import PrereqMessage
    from cylc.flow.taskdef import TaskDef


# Task status names and meanings.
# Held back from job submission due to un-met prerequisites:
TASK_STATUS_WAITING = "waiting"
# Preparing for job submission
TASK_STATUS_PREPARING = "preparing"
# Prerequisites unmet for too long - will never be submitted now:
TASK_STATUS_EXPIRED = "expired"
# Job submitted to run:
TASK_STATUS_SUBMITTED = "submitted"
# Job submission failed:
TASK_STATUS_SUBMIT_FAILED = "submit-failed"
# Job submission failed but will try again soon:
# Job execution started, but not completed yet:
TASK_STATUS_RUNNING = "running"
# Job execution completed successfully:
TASK_STATUS_SUCCEEDED = "succeeded"
# Job execution failed:
TASK_STATUS_FAILED = "failed"
# Job execution failed, but will try again soon:

TASK_STATUS_DESC = {
    TASK_STATUS_WAITING:
        'Waiting for dependencies to be satisfied.',
    TASK_STATUS_EXPIRED:
        'Execution skipped.',
    TASK_STATUS_PREPARING:
        'Cylc is preparing a job for submission.',
    TASK_STATUS_SUBMIT_FAILED:
        'Job submission has failed.',
    TASK_STATUS_SUBMITTED:
        'Job has been submitted.',
    TASK_STATUS_RUNNING:
        'Job is running.',
    TASK_STATUS_FAILED:
        'Job has returned non-zero exit code.',
    TASK_STATUS_SUCCEEDED:
        'Job has returned zero exit code.'
}

# Task statuses ordered according to task runtime progression.
TASK_STATUSES_ORDERED = [
    TASK_STATUS_WAITING,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED
]

# Task statuses ordered according to display importance
TASK_STATUS_DISPLAY_ORDER = [
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
]

TASK_STATUSES_ALL = set(TASK_STATUSES_ORDERED)

# Tasks statuses to show in restricted monitoring mode.
TASK_STATUSES_RESTRICTED = {
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
}

# Tasks statuses to show in restricted monitoring mode.
TASK_STATUSES_NO_JOB_FILE = {
    TASK_STATUS_WAITING,
    TASK_STATUS_PREPARING,
    TASK_STATUS_EXPIRED,
}

# Task statuses we can manually reset a task TO.
TASK_STATUSES_CAN_RESET_TO = {
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_WAITING,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
}

# Task statuses that are final.
TASK_STATUSES_SUCCESS = {
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUCCEEDED,
}
TASK_STATUSES_FAILURE = {
    TASK_STATUS_FAILED,
    TASK_STATUS_SUBMIT_FAILED,
}
TASK_STATUSES_FINAL = TASK_STATUSES_SUCCESS | TASK_STATUSES_FAILURE

# Task statuses that are never active.
# For tasks that have never been submitted, but excluding:
# - expired: which is effectively the "succeeded" final state.
# - held: which is placeholder state, not a real state.
TASK_STATUSES_NEVER_ACTIVE = {
    TASK_STATUS_WAITING,
    TASK_STATUS_PREPARING,
}

# Task statuses that are externally active
TASK_STATUSES_ACTIVE = {
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
}

# Mapping between task outputs and their corresponding states
TASK_STATE_MAP = {
    # status: trigger
    TASK_STATUS_WAITING: None,
    TASK_STATUS_EXPIRED: TASK_OUTPUT_EXPIRED,
    TASK_STATUS_PREPARING: None,
    TASK_STATUS_SUBMIT_FAILED: TASK_OUTPUT_SUBMIT_FAILED,
    TASK_STATUS_SUBMITTED: TASK_OUTPUT_SUBMITTED,
    TASK_STATUS_RUNNING: TASK_OUTPUT_STARTED,
    TASK_STATUS_FAILED: TASK_OUTPUT_FAILED,
    TASK_STATUS_SUCCEEDED: TASK_OUTPUT_SUCCEEDED,
}


def status_leq(status_a, status_b):
    """"Return True if status_a <= status_b"""
    return (TASK_STATUSES_ORDERED.index(status_a) <=
            TASK_STATUSES_ORDERED.index(status_b))


def status_geq(status_a, status_b):
    """"Return True if status_a >= status_b"""
    return (TASK_STATUSES_ORDERED.index(status_a) >=
            TASK_STATUSES_ORDERED.index(status_b))


class TaskState:
    """Task status and utilities.

    Attributes:
        .external_triggers (dict):
            External triggers as {trigger (str): satisfied (boolean), ...}.
        .is_held (bool):
            True if the task is held else False.
        .is_queued (bool):
            True if the task is queued else False.
        .is_runahead (bool):
            True if the task is runahead limited else False.
            Automatically true until released by the scheduler.
        .is_updated (boolean):
            Has the status been updated since previous update?
        .kill_failed (boolean):
            Has a job kill attempt failed since previous status change?
        .outputs (cylc.flow.task_outputs.TaskOutputs):
            Known outputs of the task.
        .prerequisites (list<cylc.flow.prerequisite.Prerequisite>):
            List of prerequisites of the task.
        .status (str):
            The current status of the task.
        .suicide_prerequisites (list<cylc.flow.prerequisite.Prerequisite>):
            List of prerequisites that will cause the task to suicide.
        .time_updated (str):
            Time string of latest update time.
        .xtriggers (dict):
            xtriggers as {trigger (str): satisfied (boolean), ...}.
    """

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = [
        "external_triggers",
        "is_held",
        "is_queued",
        "is_runahead",
        "is_updated",
        "kill_failed",
        "outputs",
        "prerequisites",
        "status",
        "suicide_prerequisites",
        "time_updated",
        "xtriggers",
    ]

    def __init__(self, tdef, point, status, is_held):
        self.status = status
        self.is_held = is_held
        self.is_queued = False
        self.is_runahead = True
        self.is_updated = False
        self.time_updated = None

        # Prerequisites.
        self.prerequisites: List[Prerequisite] = []
        self.suicide_prerequisites: List[Prerequisite] = []
        self._add_prerequisites(point, tdef)

        # External Triggers.
        self.external_triggers = {}
        for ext in tdef.external_triggers:
            # Allow cycle-point-specific external triggers - GitHub #1893.
            if '$CYLC_TASK_CYCLE_POINT' in ext:
                ext = ext.replace('$CYLC_TASK_CYCLE_POINT', str(point))
            # set unsatisfied
            self.external_triggers[ext] = False

        # xtriggers (represented by labels) satisfied or not
        self.xtriggers = {}
        self._add_xtriggers(point, tdef)

        # Message outputs.
        self.outputs = TaskOutputs(tdef)
        self.kill_failed = False

    def __str__(self):
        """Print status(is_held)(is_queued)(is_runahead)."""
        ret = self.status
        if self.is_held:
            ret += '(held)'
        if self.is_queued:
            ret += '(queued)'
        if self.is_runahead:
            ret += '(runahead)'
        return ret

    def __call__(
        self,
        *status: Optional[str],
        is_held: Optional[bool] = None,
        is_queued: Optional[bool] = None,
        is_runahead: Optional[bool] = None,
    ) -> bool:
        """Compare task state attributes.

        Args:
            status:
                Check if the task status is one of the ones provided, or
                do not check the task state if None.
            is_held:
                Check the task is_held attribute is the same as provided, or
                do not check the is_held attribute if None.
            is_queued:
                Check the task is_queued attribute is the same as provided, or
                do not check the is_queued attribute if None.
            is_runahead:
                Check the task is_runahead attribute is as provided, or
                do not check the is_runahead attribute if None.

        """
        return (
            (
                not status
                or self.status in status
            ) and (
                is_held is None
                or self.is_held == is_held
            ) and (
                is_queued is None
                or self.is_queued == is_queued
            ) and (
                is_runahead is None
                or self.is_runahead == is_runahead
            )
        )

    def satisfy_me(
        self,
        outputs: Iterable['Tokens'],
        forced: bool = False,
    ) -> Set['Tokens']:
        """Try to satisfy my prerequisites with given outputs.

        Return which outputs I actually depend on.
        """
        valid: Set[Tokens] = set()
        for prereq in (*self.prerequisites, *self.suicide_prerequisites):
            valid.update(
                prereq.satisfy_me(outputs, forced)
            )
        return valid

    def xtriggers_all_satisfied(self):
        """Return True if all xtriggers are satisfied."""
        return all(self.xtriggers.values())

    def external_triggers_all_satisfied(self):
        """Return True if all external triggers are satisfied."""
        return all(self.external_triggers.values())

    def prerequisites_all_satisfied(self):
        """Return True if (non-suicide) prerequisites are fully satisfied."""
        return all(preq.is_satisfied() for preq in self.prerequisites)

    def prerequisites_are_not_all_satisfied(self):
        """Return True if (any) prerequisites are not fully satisfied."""
        return (not self.prerequisites_all_satisfied() or
                not self.suicide_prerequisites_all_satisfied())

    def suicide_prerequisites_all_satisfied(self):
        """Return True if all suicide prerequisites are satisfied."""
        return all(preq.is_satisfied() for preq in self.suicide_prerequisites)

    def prerequisites_get_target_points(self):
        """Return a list of cycle points targeted by each prerequisite."""
        return {
            point
            for prerequisite in self.prerequisites
            for point in prerequisite.get_target_points()
        }

    def prerequisites_eval_all(self) -> None:
        """Evaluate satisifaction of all prerequisites and
        suicide prerequisites.

        Provides validation - will abort on illegal trigger expressions.
        """
        for preqs in [self.prerequisites, self.suicide_prerequisites]:
            for preq in preqs:
                preq.is_satisfied()

    def set_prerequisites_all_satisfied(self):
        """Set prerequisites to all satisfied."""
        for prereq in self.prerequisites:
            prereq.set_satisfied()

    def get_resolved_dependencies(self):
        """Return a list of dependencies which have been met for this task.

        E.G: ['1/foo', '2/bar']

        The returned list is sorted to allow comparison with reference run
        task with lots of near-simultaneous triggers.

        """
        return sorted(
            dep
            for prereq in self.prerequisites
            for dep in prereq.get_satisfied_dependencies()
        )

    def reset(
        self, status=None, is_held=None, is_queued=None, is_runahead=None,
        forced=False
    ):
        """Change status.

        Args:
            status (str):
                Task status to reset to or None to leave the status unchanged.
            is_held (bool):
                Set the task to be held or not, or None to leave this property
                unchanged.
            forced (bool):
                If called as a result of a forced change (via "cylc set")

        Returns:
            Whether state changed or not (bool)

        """
        req = status

        if forced and req in [TASK_STATUS_SUBMITTED, TASK_STATUS_RUNNING]:
            # Can't force change to an active state because there's no job.
            return False

        current_status = (
            self.status,
            self.is_held,
            self.is_queued,
            self.is_runahead
        )
        requested_status = (
            status if status is not None else self.status,
            is_held if is_held is not None else self.is_held,
            is_queued if is_queued is not None else self.is_queued,
            is_runahead if is_runahead is not None else self.is_runahead
        )
        if current_status == requested_status:
            # no change - do nothing
            return False

        # perform the state change
        self.status, self.is_held, self.is_queued, self.is_runahead = (
            requested_status
        )

        self.time_updated = get_current_time_string()
        self.is_updated = True
        self.kill_failed = False

        if status is None:
            # NOTE: status is None if the task is being released
            status = self.status

        return True

    def is_gt(self, status):
        """"Return True if self.status > status."""
        return (TASK_STATUSES_ORDERED.index(self.status) >
                TASK_STATUSES_ORDERED.index(status))

    def is_gte(self, status):
        """"Return True if self.status >= status."""
        return (TASK_STATUSES_ORDERED.index(self.status) >=
                TASK_STATUSES_ORDERED.index(status))

    def _add_prerequisites(self, point: 'PointBase', tdef: 'TaskDef'):
        """Add task prerequisites."""
        # Triggers for sequence_i only used if my cycle point is a
        # valid member of sequence_i's sequence of cycle points.

        # Use dicts to avoid generating duplicate prerequisites from sequences
        # with coincident cycle points.
        prerequisites: Dict[int, Prerequisite] = {}
        suicide_prerequisites: Dict[int, Prerequisite] = {}

        for sequence, dependencies in tdef.dependencies.items():
            if not sequence.is_valid(point):
                continue
            for dependency in dependencies:
                cpre = dependency.get_prerequisite(point, tdef)
                if dependency.suicide:
                    suicide_prerequisites[cpre.instantaneous_hash()] = cpre
                else:
                    prerequisites[cpre.instantaneous_hash()] = cpre

        if tdef.sequential:
            # Add a previous-instance succeeded prerequisite.
            adjusted = []
            for seq in tdef.sequences:
                prv = seq.get_nearest_prev_point(point)
                if prv:
                    # None if out of sequence bounds.
                    adjusted.append(prv)
            if adjusted:
                p_prev = max(adjusted)
                cpre = Prerequisite(point)
                cpre[(p_prev, tdef.name, TASK_STATUS_SUCCEEDED)] = (
                    p_prev < tdef.start_point
                )
                cpre.set_condition(tdef.name)
                prerequisites[cpre.instantaneous_hash()] = cpre

        self.suicide_prerequisites = list(suicide_prerequisites.values())
        self.prerequisites = list(prerequisites.values())

    def add_xtrigger(self, label, satisfied=False):
        self.xtriggers[label] = satisfied

    def get_xtrigger(self, label):
        return self.xtriggers[label]

    def _add_xtriggers(self, point, tdef):
        """Add task xtriggers valid for the current sequence.

        Initialize each one to unsatisfied.
        """
        # Triggers for sequence_i only used if my cycle point is a
        # valid member of sequence_i's sequence of cycle points.
        for sequence, xtrig_labels in tdef.xtrig_labels.items():
            if not sequence.is_valid(point):
                continue
            for xtrig_label in xtrig_labels:
                self.add_xtrigger(xtrig_label)

    def get_unsatisfied_prerequisites(self) -> List['PrereqMessage']:
        return [
            key
            for prereq in self.prerequisites if not prereq.is_satisfied()
            for key, satisfied in prereq.items() if not satisfied
        ]

    def any_satisfied_prerequisite_tasks(self) -> bool:
        """Return True if any of this task's prerequisite tasks are
        satisfied."""
        return any(
            satisfied
            for prereq in self.prerequisites
            for satisfied in prereq._satisfied.values()
        )

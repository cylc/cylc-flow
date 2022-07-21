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

"""Task state related logic."""


from cylc.flow.prerequisite import Prerequisite
from cylc.flow.task_outputs import (
    TaskOutputs,
    TASK_OUTPUT_EXPIRED, TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED)
from cylc.flow.wallclock import get_current_time_string


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

# Task statuses that can be manually triggered.
TASK_STATUSES_TRIGGERABLE = {
    TASK_STATUS_WAITING,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
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
        ._is_satisfied (boolean):
            Are prerequisites satisfied?
        ._suicide_is_satisfied (boolean):
            Are prerequisites to trigger suicide satisfied?
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
        "_is_satisfied",
        "_suicide_is_satisfied",
    ]

    def __init__(self, tdef, point, status, is_held):
        self.status = status
        self.is_held = is_held
        self.is_queued = False
        self.is_runahead = True
        self.is_updated = False
        self.time_updated = None

        self._is_satisfied = None
        self._suicide_is_satisfied = None

        # Prerequisites.
        self.prerequisites = []
        self.suicide_prerequisites = []
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
            self, *status, is_held=None, is_queued=None, is_runahead=None):
        """Compare task state attributes.

        Args:
            status (str/list/None):
                ``str``
                    Check if the task status is the same as the one provided
                ``list``
                    Check if the task status is one of the ones provided
                ``None``
                    Do not check the task state.
            is_held (bool):
                ``bool``
                    Check the task is_held attribute is the same as provided
                ``None``
                    Do not check the is_held attribute
            is_queued (bool):
                ``bool``
                    Check the task is_queued attribute is the same as provided
                ``None``
                    Do not check the is_queued attribute
            is_runahead (bool):
                ``bool``
                    Check the task is_runahead attribute is as provided
                ``None``
                    Do not check the is_runahead attribute

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

    def satisfy_me(self, all_task_outputs):
        """Attempt to get my prerequisites satisfied."""
        for prereqs in [self.prerequisites, self.suicide_prerequisites]:
            for prereq in prereqs:
                if prereq.satisfy_me(all_task_outputs):
                    self._is_satisfied = None
                    self._suicide_is_satisfied = None

    def xtriggers_all_satisfied(self):
        """Return True if all xtriggers are satisfied."""
        return all(self.xtriggers.values())

    def external_triggers_all_satisfied(self):
        """Return True if all external triggers are satisfied."""
        return all(self.external_triggers.values())

    def prerequisites_all_satisfied(self):
        """Return True if (non-suicide) prerequisites are fully satisfied."""
        if self._is_satisfied is None:
            self._is_satisfied = all(
                preq.is_satisfied() for preq in self.prerequisites)
        return self._is_satisfied

    def prerequisites_are_not_all_satisfied(self):
        """Return True if (any) prerequisites are not fully satisfied."""
        return (not self.prerequisites_all_satisfied() or
                not self.suicide_prerequisites_all_satisfied())

    def suicide_prerequisites_all_satisfied(self):
        """Return True if all suicide prerequisites are satisfied."""
        if self._suicide_is_satisfied is None:
            self._suicide_is_satisfied = all(
                preq.is_satisfied() for preq in self.suicide_prerequisites)
        return self._suicide_is_satisfied

    def prerequisites_get_target_points(self):
        """Return a list of cycle points targeted by each prerequisite."""
        return {
            point
            for prerequisite in self.prerequisites
            for point in prerequisite.get_target_points()
        }

    def prerequisites_eval_all(self):
        """Set all prerequisites to satisfied."""
        # (Validation: will abort on illegal trigger expressions.)
        for preqs in [self.prerequisites, self.suicide_prerequisites]:
            for preq in preqs:
                preq.is_satisfied()

    def set_prerequisites_all_satisfied(self):
        """Set prerequisites to all satisfied."""
        for prereq in self.prerequisites:
            prereq.set_satisfied()
        self._is_satisfied = None

    def set_prerequisites_not_satisfied(self):
        """Reset prerequisites."""
        for prereq in self.prerequisites:
            prereq.set_not_satisfied()
        self._is_satisfied = None

    def get_resolved_dependencies(self):
        """Return a list of dependencies which have been met for this task.

        E.G: ['1/foo', '2/bar']

        The returned list is sorted to allow comparison with reference run
        task with lots of near-simultaneous triggers.

        """
        return sorted(
            dep
            for prereq in self.prerequisites
            for dep in prereq.get_resolved_dependencies()
        )

    def reset(
            self, status=None, is_held=None, is_queued=None, is_runahead=None):
        """Change status, and manipulate outputs and prerequisites accordingly.

        Outputs are manipulated on manual state reset to reflect the new task
        status. Since spawn-on-demand implementation, state reset is only used
        for internal state changes.

        Args:
            status (str):
                Task status to reset to or None to leave the status unchanged.
            is_held (bool):
                Set the task to be held or not, or None to leave this property
                unchanged.

        Returns:
            returns: whether state change or not (bool)

        """
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

        # perform the actual state change
        self.status, self.is_held, self.is_queued, self.is_runahead = (
            requested_status
        )

        self.time_updated = get_current_time_string()
        self.is_updated = True

        if is_held:
            # only reset task outputs if not setting task to held
            # https://github.com/cylc/cylc-flow/pull/2116
            return True

        self.kill_failed = False

        # Set standard outputs in accordance with task state.
        if status is None:
            # NOTE: status is None if the task is being released
            status = self.status
        if status_leq(status, TASK_STATUS_SUBMITTED):
            self.outputs.set_all_incomplete()
        self.outputs.set_completion(
            TASK_OUTPUT_EXPIRED, status == TASK_STATUS_EXPIRED)
        self.outputs.set_completion(
            TASK_OUTPUT_SUBMITTED, status_geq(status, TASK_STATUS_SUBMITTED))
        self.outputs.set_completion(
            TASK_OUTPUT_STARTED, status_geq(status, TASK_STATUS_RUNNING))
        self.outputs.set_completion(
            TASK_OUTPUT_SUBMIT_FAILED, status == TASK_STATUS_SUBMIT_FAILED)
        self.outputs.set_completion(
            TASK_OUTPUT_SUCCEEDED, status == TASK_STATUS_SUCCEEDED)
        self.outputs.set_completion(
            TASK_OUTPUT_FAILED, status == TASK_STATUS_FAILED)

        return True

    def is_gt(self, status):
        """"Return True if self.status > status."""
        return (TASK_STATUSES_ORDERED.index(self.status) >
                TASK_STATUSES_ORDERED.index(status))

    def _add_prerequisites(self, point, tdef):
        """Add task prerequisites."""
        # Triggers for sequence_i only used if my cycle point is a
        # valid member of sequence_i's sequence of cycle points.
        self._is_satisfied = None
        self._suicide_is_satisfied = None

        for sequence, dependencies in tdef.dependencies.items():
            if not sequence.is_valid(point):
                continue
            for dependency in dependencies:
                cpre = dependency.get_prerequisite(point, tdef)
                if dependency.suicide:
                    self.suicide_prerequisites.append(cpre)
                else:
                    self.prerequisites.append(cpre)

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
                cpre = Prerequisite(point, tdef.start_point)
                cpre.add(tdef.name, p_prev, TASK_STATUS_SUCCEEDED,
                         p_prev < tdef.start_point)
                cpre.set_condition(tdef.name)
                self.prerequisites.append(cpre)

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

    def get_unsatisfied_prerequisites(self):
        unsat = []
        for prereq in self.prerequisites:
            if prereq.is_satisfied():
                continue
            for key, val in prereq.satisfied.items():
                if val:
                    continue
                unsat.append(key)
        return unsat

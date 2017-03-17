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

"""Task state related logic."""


from cylc.cycling.loader import get_point_relative
import cylc.flags as flags
from cylc.prerequisite import Prerequisite
from cylc.suite_logging import LOG
from cylc.task_id import TaskID
from cylc.task_outputs import (
    TaskOutputs,
    TASK_OUTPUT_EXPIRED, TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED)
from cylc.wallclock import get_current_time_string


# Task status names.
TASK_STATUS_RUNAHEAD = "runahead"
TASK_STATUS_WAITING = "waiting"
TASK_STATUS_HELD = "held"
TASK_STATUS_QUEUED = "queued"
TASK_STATUS_READY = "ready"
TASK_STATUS_EXPIRED = "expired"
TASK_STATUS_SUBMITTED = "submitted"
TASK_STATUS_SUBMIT_FAILED = "submit-failed"
TASK_STATUS_SUBMIT_RETRYING = "submit-retrying"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_SUCCEEDED = "succeeded"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_RETRYING = "retrying"

# Tasks statuses ordered according to task runtime progression.
TASK_STATUSES_ORDERED = [
    TASK_STATUS_RUNAHEAD,
    TASK_STATUS_WAITING,
    TASK_STATUS_HELD,
    TASK_STATUS_QUEUED,
    TASK_STATUS_READY,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING
]

TASK_STATUSES_ALL = set(TASK_STATUSES_ORDERED)

# Tasks statuses to show in restricted monitoring mode.
TASK_STATUSES_RESTRICTED = set([
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING
])

# Task statuses we can manually reset a task TO.
TASK_STATUSES_CAN_RESET_TO = set([
    TASK_STATUS_WAITING,
    TASK_STATUS_HELD,
    TASK_STATUS_READY,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED
])

# Task statuses that are final.
TASK_STATUSES_FINAL = set([
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_SUBMIT_FAILED,
])

# Task statuses that are to be externally active
TASK_STATUSES_TO_BE_ACTIVE = set([
    TASK_STATUS_QUEUED,
    TASK_STATUS_READY,
    TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RETRYING,
])

# Task statuses that are externally active, i.e. pollable and killable
TASK_STATUSES_ACTIVE = set([
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
])

# Task statuses in which tasks cannot be considered stalled
TASK_STATUSES_NOT_STALLED = TASK_STATUSES_ACTIVE | TASK_STATUSES_TO_BE_ACTIVE

# Task statuses that can be manually triggered.
TASK_STATUSES_TRIGGERABLE = set([
    TASK_STATUS_WAITING,
    TASK_STATUS_HELD,
    TASK_STATUS_QUEUED,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING
])

# Task statues that that have viewable job logs.
TASK_STATUSES_WITH_JOB_LOGS = set([
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING
])

# Task statuses that have viewable job script (and activity logs). .
TASK_STATUSES_WITH_JOB_SCRIPT = set([
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING
])

# Tasks statuses to auto-exand in the gcylc tree view.
TASK_STATUSES_AUTO_EXPAND = set([
    TASK_STATUS_QUEUED,
    TASK_STATUS_READY,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
])


class TaskState(object):
    """Task status and utilities."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["identity", "status", "hold_swap",
                 "_is_satisfied", "_suicide_is_satisfied", "prerequisites",
                 "suicide_prerequisites", "external_triggers", "outputs",
                 "kill_failed", "time_updated",
                 "submission_timer_timeout", "execution_timer_timeout"]

    def __init__(self, tdef, point, status, hold_swap):
        self.identity = TaskID.get(tdef.name, str(point))
        self.status = status
        self.hold_swap = hold_swap
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

        # Message outputs.
        self.outputs = TaskOutputs(TaskID.get(tdef.name, str(point)))
        for outp in tdef.outputs:
            self.outputs.add(outp.get_string(point))

        # Standard outputs.
        self.outputs.add(TASK_OUTPUT_SUBMITTED)
        self.outputs.add(TASK_OUTPUT_STARTED)
        self.outputs.add(TASK_OUTPUT_SUCCEEDED)

        self.kill_failed = False

        # TODO - these are here because current use in reset_state(); should be
        # disentangled and put in the task_proxy module.
        self.submission_timer_timeout = None
        self.execution_timer_timeout = None

    def satisfy_me(self, task_output_msgs, task_outputs):
        """Attempt to get my prerequisites satisfied."""
        for preqs in [self.prerequisites, self.suicide_prerequisites]:
            for preq in preqs:
                if preq.satisfy_me(task_output_msgs, task_outputs):
                    self._is_satisfied = None
                    self._suicide_is_satisfied = None

    def prerequisites_are_all_satisfied(self):
        """Return True if (non-suicide) prerequisites are fully satisfied."""
        if self._is_satisfied is None:
            self._is_satisfied = all(
                preq.is_satisfied() for preq in self.prerequisites)
        return self._is_satisfied

    def prerequisites_are_not_all_satisfied(self):
        """Return True if (any) prerequisites are not fully satisfied."""
        return (not self.prerequisites_are_all_satisfied() or
                not self.suicide_prerequisites_are_all_satisfied())

    def suicide_prerequisites_are_all_satisfied(self):
        """Return True if all suicide prerequisites are satisfied."""
        if self._suicide_is_satisfied is None:
            self._suicide_is_satisfied = all(
                preq.is_satisfied() for preq in self.suicide_prerequisites)
        return self._suicide_is_satisfied

    def prerequisites_get_target_points(self):
        """Return a list of cycle points targeted by each prerequisite."""
        points = []
        for preq in self.prerequisites:
            points += preq.get_target_points()
        return points

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

    def prerequisites_dump(self, list_prereqs=False):
        """Dump prerequisites."""
        res = []
        if list_prereqs:
            for prereq in self.prerequisites:
                for task in sorted(prereq.labels):
                    res.append(task)
        else:
            for preq in self.prerequisites:
                res += preq.dump()
        return res

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

    def unset_special_outputs(self):
        """Remove special outputs added for triggering purposes.

        (Otherwise they appear as incomplete outputs when the task finishes).

        """
        self.kill_failed = False
        self.outputs.remove(TASK_OUTPUT_EXPIRED)
        self.outputs.remove(TASK_OUTPUT_SUBMIT_FAILED)
        self.outputs.remove(TASK_OUTPUT_FAILED)

    def release(self):
        """Reset to my pre-held state, if not beyond the stop point."""
        if self.status != TASK_STATUS_HELD:
            return
        elif self.hold_swap is None:
            self.reset_state(TASK_STATUS_WAITING)
        elif self.hold_swap == TASK_STATUS_HELD:
            self.hold_swap = None
        else:
            self.submission_timer_timeout = None
            self.execution_timer_timeout = None
            self.reset_state(self.hold_swap)

    def set_state(self, status):
        """Set, log and record task status (normal change, not forced - don't
        update task_events table)."""
        if self.status == self.hold_swap:
            self.hold_swap = None
        if status == self.status and self.hold_swap is None:
            return
        o_status, o_hold_swap = self.status, self.hold_swap
        if status == TASK_STATUS_HELD:
            self.hold_swap = self.status
        elif (self.hold_swap == TASK_STATUS_HELD and
                status not in TASK_STATUSES_FINAL):
            self.hold_swap = status
            status = TASK_STATUS_HELD
        elif self.hold_swap:
            self.hold_swap = None
        self.status = status
        self.time_updated = get_current_time_string()
        flags.iflag = True
        # Log
        message = str(o_status)
        if o_hold_swap:
            message += " (%s)" % o_hold_swap
        message += " => %s" % self.status
        if self.hold_swap:
            message += " (%s)" % self.hold_swap
        LOG.debug(message, itask=self.identity)

    def reset_state(self, status):
        """Reset status of task."""
        if status == TASK_STATUS_HELD:
            if self.status in TASK_STATUSES_ACTIVE:
                self.hold_swap = TASK_STATUS_HELD
                return
            if self.status not in [
                    TASK_STATUS_WAITING, TASK_STATUS_QUEUED,
                    TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RETRYING]:
                return
        elif status == TASK_STATUS_EXPIRED:
            self.set_prerequisites_all_satisfied()
            self.unset_special_outputs()
            self.outputs.set_all_incomplete()
            self.outputs.add(TASK_OUTPUT_EXPIRED, True)
        elif status == TASK_STATUS_WAITING:
            self.set_prerequisites_not_satisfied()
            self.unset_special_outputs()
            self.outputs.set_all_incomplete()
        elif status == TASK_STATUS_READY:
            self.set_prerequisites_all_satisfied()
            self.unset_special_outputs()
            self.outputs.set_all_incomplete()
        elif status == TASK_STATUS_SUCCEEDED:
            self.set_prerequisites_all_satisfied()
            self.unset_special_outputs()
            # TODO - for message outputs this should be optional (see #1551):
            self.outputs.set_all_completed()
        elif status == TASK_STATUS_FAILED:
            self.set_prerequisites_all_satisfied()
            self.outputs.set_all_incomplete()
            # Set a new failed output just as if a failure message came in
            self.outputs.add(TASK_OUTPUT_FAILED, True)

        self.submission_timer_timeout = None
        self.execution_timer_timeout = None
        return self.set_state(status)

    def is_ready_to_run(self, retry_delay_done, start_time_reached):
        """With current status, is the task ready to run?"""
        return (
            (
                (
                    self.status == TASK_STATUS_WAITING and
                    self.prerequisites_are_all_satisfied() and
                    all(self.external_triggers.values())
                ) or
                (
                    self.status in [TASK_STATUS_SUBMIT_RETRYING,
                                    TASK_STATUS_RETRYING] and
                    retry_delay_done
                )
            ) and start_time_reached
        )

    def is_greater_than(self, status):
        """"Return True if self.status > status."""
        return (TASK_STATUSES_ORDERED.index(self.status) >
                TASK_STATUSES_ORDERED.index(status))

    def set_expired(self):
        """Manipulate state for task expired."""
        self.reset_state(TASK_STATUS_EXPIRED)

    def set_ready_to_submit(self):
        """Manipulate state just prior to job submission."""
        self.set_state(TASK_STATUS_READY)

    def set_submit_failed(self):
        """Manipulate state after job submission failure."""
        self.set_state(TASK_STATUS_SUBMIT_FAILED)
        self.outputs.remove(TASK_OUTPUT_SUBMITTED)
        self.outputs.add(TASK_OUTPUT_SUBMIT_FAILED, True)

    def set_submit_retry(self):
        """Manipulate state for job submission retry."""
        self.outputs.remove(TASK_OUTPUT_SUBMITTED)
        self.set_state(TASK_STATUS_SUBMIT_RETRYING)
        self.set_prerequisites_all_satisfied()

    def set_submit_succeeded(self):
        """Set status to submitted."""
        if not self.outputs.is_completed(TASK_OUTPUT_SUBMITTED):
            self.outputs.set_completed(TASK_OUTPUT_SUBMITTED)
            # Allow submitted tasks to spawn even if nothing else is happening.
            flags.pflag = True
        if self.status == TASK_STATUS_READY:
            # In rare occassions, the submit command of a batch system has sent
            # the job to its server, and the server has started the job before
            # the job submit command returns.
            self.set_state(TASK_STATUS_SUBMITTED)
            return True
        else:
            return False

    def set_execution_succeeded(self, msg_was_polled):
        """Manipulate state for job execution success."""
        self.set_state(TASK_STATUS_SUCCEEDED)
        warnings = []
        if not self.outputs.all_completed():
            err = "Succeeded with unreported outputs:"
            for key in self.outputs.not_completed:
                err += "\n  " + key
            warnings.append(err)
            if msg_was_polled:
                # Assume all outputs complete (e.g. poll at restart).
                # TODO - just poll for outputs in the job status file.
                warnings.append("Assuming ALL outputs completed.")
                self.outputs.set_all_completed()
            else:
                # A succeeded task MUST have submitted and started.
                # TODO - just poll for outputs in the job status file?
                for output in [TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED]:
                    if not self.outputs.is_completed(output):
                        warnings.append(
                            "Assuming output completed:  \n %s" % output)
                        self.outputs.set_completed(output)
        return warnings

    def set_execution_failed(self):
        """Manipulate state for job execution failure."""
        self.reset_state(TASK_STATUS_FAILED)

    def set_execution_retry(self):
        """Manipulate state for job execution retry."""
        self.set_state(TASK_STATUS_RETRYING)
        self.set_prerequisites_all_satisfied()

    def _add_prerequisites(self, point, tdef):
        """Add task prerequisites."""
        # self.triggers[sequence] = [triggers for sequence]
        # Triggers for sequence_i only used if my cycle point is a
        # valid member of sequence_i's sequence of cycle points.
        self._is_satisfied = None
        self._suicide_is_satisfied = None
        identity = TaskID.get(tdef.name, str(point))

        for sequence, exps in tdef.triggers.items():
            for ctrig, exp in exps:
                key = ctrig.keys()[0]
                if not sequence.is_valid(point):
                    # This trigger is not valid for current cycle (see NOTE
                    # just above)
                    continue

                cpre = Prerequisite(identity, point, tdef.start_point)

                for label in ctrig:
                    trig = ctrig[label]
                    if trig.graph_offset_string is not None:
                        prereq_offset_point = get_point_relative(
                            trig.graph_offset_string, point)
                        if prereq_offset_point > point:
                            prereq_offset = prereq_offset_point - point
                            if (tdef.max_future_prereq_offset is None or
                                    (prereq_offset >
                                     tdef.max_future_prereq_offset)):
                                tdef.max_future_prereq_offset = (
                                    prereq_offset)
                        cpre.add(trig.get_prereq(point), label,
                                 ((prereq_offset_point < tdef.start_point) &
                                  (point >= tdef.start_point)))
                    else:
                        cpre.add(trig.get_prereq(point), label)
                cpre.set_condition(exp)
                if ctrig[key].suicide:
                    self.suicide_prerequisites.append(cpre)
                else:
                    self.prerequisites.append(cpre)

        if tdef.sequential:
            # Add a previous-instance succeeded prerequisite.
            p_prev = None
            adjusted = []
            for seq in tdef.sequences:
                prv = seq.get_nearest_prev_point(point)
                if prv:
                    # None if out of sequence bounds.
                    adjusted.append(prv)
            if adjusted:
                p_prev = max(adjusted)
                cpre = Prerequisite(identity, point, tdef.start_point)
                prereq = "%s %s" % (TaskID.get(tdef.name, p_prev),
                                    TASK_STATUS_SUCCEEDED)
                label = tdef.name
                cpre.add(prereq, label, p_prev < tdef.start_point)
                cpre.set_condition(label)
                self.prerequisites.append(cpre)

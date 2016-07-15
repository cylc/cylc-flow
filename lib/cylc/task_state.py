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

"""Task state related logic."""


from logging import WARNING, INFO, DEBUG

import cylc.flags as flags
from cylc.task_outputs import TaskOutputs
from cylc.prerequisite import Prerequisite
from cylc.cycling.loader import get_point_relative
from cylc.task_id import TaskID
from cylc.task_outputs import (
    TASK_OUTPUT_EXPIRED, TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED)


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

# Task statuses that are killable.
TASK_STATUSES_KILLABLE = set([
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING
])

# Task statuses that are externally active.
TASK_STATUSES_ACTIVE = TASK_STATUSES_KILLABLE

# Task statuses that are pollable.
TASK_STATUSES_POLLABLE = set([
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING
])

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


class TaskStateError(ValueError):
    """Illegal task state."""
    pass


class TaskState(object):
    """Task status and utilities."""

    # Associate status names with other properties.
    _STATUS_MAP = {
        TASK_STATUS_RUNAHEAD: {
            "gtk_label": "r_unahead",  # GTK widget labels.
            "ascii_ctrl": "\033[1;37;44m"  # Terminal color control codes.
        },
        TASK_STATUS_WAITING: {
            "gtk_label": "_waiting",
            "ascii_ctrl": "\033[1;36m"
        },
        TASK_STATUS_HELD: {
            "gtk_label": "_held",
            "ascii_ctrl": "\033[1;37;43m"
        },
        TASK_STATUS_QUEUED: {
            "gtk_label": "_queued",
            "ascii_ctrl": "\033[1;38;44m"
        },
        TASK_STATUS_READY: {
            "gtk_label": "rea_dy",
            "ascii_ctrl": "\033[1;32m"
        },
        TASK_STATUS_EXPIRED: {
            "gtk_label": "e_xpired",
            "ascii_ctrl": "\033[1;37;40m"
        },
        TASK_STATUS_SUBMITTED: {
            "gtk_label": "sub_mitted",
            "ascii_ctrl": "\033[1;33m"
        },
        TASK_STATUS_SUBMIT_FAILED: {
            "gtk_label": "submit-f_ailed",
            "ascii_ctrl": "\033[1;34m"
        },
        TASK_STATUS_SUBMIT_RETRYING: {
            "gtk_label": "submit-retryin_g",
            "ascii_ctrl": "\033[1;31m"
        },
        TASK_STATUS_RUNNING: {
            "gtk_label": "_running",
            "ascii_ctrl": "\033[1;37;42m"
        },
        TASK_STATUS_SUCCEEDED: {
            "gtk_label": "_succeeded",
            "ascii_ctrl": "\033[0m"
        },
        TASK_STATUS_FAILED: {
            "gtk_label": "_failed",
            "ascii_ctrl": "\033[1;37;41m"
        },
        TASK_STATUS_RETRYING: {
            "gtk_label": "retr_ying",
            "ascii_ctrl": "\033[1;35m"
        }
    }

    @classmethod
    def get_status_prop(cls, status, key, subst=None):
        """Return property for a task status."""
        if key == "ascii_ctrl":
            if subst is not None:
                return "%s%s\033[0m" % (cls._STATUS_MAP[status][key], subst)
            else:
                return "%s%s\033[0m" % (cls._STATUS_MAP[status][key], status)
        try:
            return cls._STATUS_MAP[status][key]
        except KeyError:
            raise TaskStateError("Bad task status (%s, %s)" % (status, key))

    def __init__(self, status, point, identity, tdef, db_events_insert,
                 db_update_status, log):

        self.status = status
        self.identity = identity
        self.db_events_insert = db_events_insert
        self.db_update_status = db_update_status
        self.log = log

        self._recalc_satisfied = True
        self._is_satisfied = False
        self._suicide_is_satisfied = False

        # Prerequisites.
        self.prerequisites = []
        self.suicide_prerequisites = []
        self._add_prerequisites(point, identity, tdef)

        # External Triggers.
        self.external_triggers = {}
        for ext in tdef.external_triggers:
            # set unsatisfied
            self.external_triggers[ext] = False

        # Message outputs.
        self.outputs = TaskOutputs(identity)
        for outp in tdef.outputs:
            self.outputs.add(outp.get_string(point))

        # Standard outputs.
        self.outputs.add(TASK_OUTPUT_SUBMITTED)
        self.outputs.add(TASK_OUTPUT_STARTED)
        self.outputs.add(TASK_OUTPUT_SUCCEEDED)

        self.kill_failed = False
        self.hold_on_retry = False
        self._state_pre_hold = None
        self.run_mode = tdef.run_mode

        # TODO - these are here because current use in reset_state(); should be
        # disentangled and put in the task_proxy module.
        self.submission_timer_timeout = None
        self.execution_timer_timeout = None

    def satisfy_me(self, task_output_msgs, task_outputs):
        """Attempt to get my prerequisites satisfied."""
        self._recalc_satisfied = False
        for preqs in [self.prerequisites, self.suicide_prerequisites]:
            for preq in preqs:
                if preq.satisfy_me(task_output_msgs, task_outputs):
                    self._recalc_satisfied = True

    def prerequisites_are_all_satisfied(self):
        """Return True if (non-suicide) prerequisites are fully satisfied."""
        if self._recalc_satisfied:
            self._is_satisfied = all(
                preq.is_satisfied() for preq in self.prerequisites)
        return self._is_satisfied

    def prerequisites_are_not_all_satisfied(self):
        """Return True if (any) prerequisites are not fully satisfied."""
        if self._recalc_satisfied:
            return (not self.prerequisites_are_all_satisfied() or
                    not self.suicide_prerequisites_are_all_satisfied())
        return (not self._is_satisfied or not self._suicide_is_satisfied)

    def suicide_prerequisites_are_all_satisfied(self):
        """Return True if all suicide prerequisites are satisfied."""
        if self._recalc_satisfied:
            self._suicide_is_satisfied = all(
                preq.is_satisfied() for preq in self.suicide_prerequisites)
        return self._suicide_is_satisfied

    def prerequisites_get_target_points(self):
        """Return a list of cycle points targetted by each prerequisite."""
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
        self._recalc_satisfied = True

    def set_prerequisites_not_satisfied(self):
        """Reset prerequisites."""
        for prereq in self.prerequisites:
            prereq.set_not_satisfied()
        self._recalc_satisfied = True

    def prerequisites_dump(self):
        """Dump prerequisites."""
        res = []
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
        self.hold_on_retry = False
        self.kill_failed = False
        self.outputs.remove(TASK_OUTPUT_EXPIRED)
        self.outputs.remove(TASK_OUTPUT_SUBMIT_FAILED)
        self.outputs.remove(TASK_OUTPUT_FAILED)

    def release(self):
        """Reset to my pre-held state, if not beyond the stop point."""
        self.hold_on_retry = False
        if not self.status == TASK_STATUS_HELD:
            return
        if self._state_pre_hold is None:
            self.reset_state(TASK_STATUS_WAITING)
            return
        old_status = self._state_pre_hold
        self._state_pre_hold = None
        self.log(INFO, 'held => %s' % (old_status))

        # Turn off submission and execution timeouts.
        self.submission_timer_timeout = None
        self.execution_timer_timeout = None
        self.set_state(old_status)

    def set_state(self, status):
        """Set, log and record task status (normal change, not forced - don't
        update task_events table)."""
        if status != self.status:
            flags.iflag = True
            self.log(DEBUG, '(setting: %s)' % status)
            self.status = status
            self.db_update_status()

    def reset_state(self, status):
        """Reset status of task."""
        if status == TASK_STATUS_HELD:
            if self.status in TASK_STATUSES_ACTIVE:
                self.hold_on_retry = True
                return
            if self.status not in [
                    TASK_STATUS_WAITING, TASK_STATUS_QUEUED,
                    TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RETRYING]:
                return
            self._state_pre_hold = self.status
            self.log(INFO, '%s => held' % self._state_pre_hold)

        # Turn off submission and execution timeouts.
        self.submission_timer_timeout = None
        self.execution_timer_timeout = None

        self.set_state(status)
        if status == TASK_STATUS_EXPIRED:
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
            self.hold_on_retry = False
            self.outputs.set_all_incomplete()
            # Set a new failed output just as if a failure message came in
            self.outputs.add(TASK_OUTPUT_FAILED, True)
        # TODO - handle other state resets here too, such as retrying...?

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
        if self.hold_on_retry:
            self.reset_state(TASK_STATUS_HELD)

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

    def set_executing(self):
        """Manipulate state for job execution."""
        self.set_state(TASK_STATUS_RUNNING)
        if self.run_mode == 'simulation':
            self.outputs.set_completed(TASK_OUTPUT_STARTED)

    def set_execution_succeeded(self, msg_was_polled):
        """Manipulate state for job execution success."""
        self.set_state(TASK_STATUS_SUCCEEDED)
        if not self.outputs.all_completed():
            err = "Succeeded with unreported outputs:"
            for key in self.outputs.not_completed:
                err += "\n  " + key
            self.log(WARNING, err)
            if msg_was_polled:
                # Assume all outputs complete (e.g. poll at restart).
                # TODO - just poll for outputs in the job status file.
                self.log(WARNING, "Assuming ALL outputs completed.")
                self.outputs.set_all_completed()
            else:
                # A succeeded task MUST have submitted and started.
                # TODO - just poll for outputs in the job status file?
                for output in [TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED]:
                    if not self.outputs.is_completed(output):
                        self.log(WARNING,
                                 "Assuming output completed:  \n %s" % output)
                        self.outputs.set_completed(output)

    def set_execution_failed(self):
        """Manipulate state for job execution failure."""
        self.reset_state(TASK_STATUS_FAILED)

    def set_execution_retry(self):
        """Manipulate state for job execution retry."""
        self.set_state(TASK_STATUS_RETRYING)
        self.set_prerequisites_all_satisfied()
        if self.hold_on_retry:
            self.reset_state(TASK_STATUS_HELD)

    def record_output(self, msg, msg_was_polled):
        """Record a completed output."""
        if self.outputs.exists(msg):
            if not self.outputs.is_completed(msg):
                flags.pflag = True
                self.outputs.set_completed(msg)
                self.db_events_insert(event="output completed", message=msg)
            elif not msg_was_polled:
                # This output has already been reported complete. Not an error
                # condition - maybe the network was down for a bit. Ok for
                # polling as multiple polls *should* produce the same result.
                self.log(WARNING,
                         "Unexpected output (already completed):\n  " + msg)

    def _add_prerequisites(self, point, identity, tdef):
        """Add task prerequisites."""
        # self.triggers[sequence] = [triggers for sequence]
        # Triggers for sequence_i only used if my cycle point is a
        # valid member of sequence_i's sequence of cycle points.
        self._recalc_satisfied = True

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

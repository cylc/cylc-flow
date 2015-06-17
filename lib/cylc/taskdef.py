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
"""Task definition.

NOTE on conditional and non-conditional triggers: all plain triggers
(for a single task) are held in a single prerequisite object; but one
such object is held for each conditional trigger. This has
implications for global detection of duplicated prerequisites
(detection is currently disabled).

"""

from cylc.cycling.loader import get_point_relative, get_interval
from cylc.task_id import TaskID


class TaskDefError(Exception):
    """Exception raise for errors in TaskDef initialization."""

    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.msg = msg

    def __str__(self):
        return "ERROR: %s" % self.msg


class TaskDef(object):
    """Task definition."""

    def __init__(self, name, rtcfg, run_mode, start_point):
        if not TaskID.is_valid_name(name):
            raise TaskDefError("Illegal task name: %s" % name)

        self.run_mode = run_mode
        self.rtconfig = rtcfg
        self.start_point = start_point

        self.sequences = []
        self.implicit_sequences = []  # Implicit sequences are deprecated.
        self.used_in_offset_trigger = False

        # some defaults
        self.max_future_prereq_offset = None
        self.intercycle_offsets = []
        self.sequential = False
        self.is_coldstart = False
        self.suite_polling_cfg = {}

        self.clocktrigger_offset = None
        self.expiration_offset = None
        self.namespace_hierarchy = []
        # triggers[0,6] = [ A, B:1, C(T-6), ... ]
        self.triggers = {}
        # cond[6,18] = [ '(A & B)|C', 'C | D | E', ... ]
        self.cond_triggers = {}
        # list of explicit internal outputs; change to dict if need to vary per
        # cycle.
        self.outputs = []

        self.external_triggers = []

        self.name = name
        self.elapsed_times = []
        self.mean_total_elapsed_time = None

    def add_trigger(self, trigger, sequence):
        """Add trigger to a named sequence."""
        if sequence not in self.triggers:
            self.triggers[sequence] = []
        self.triggers[sequence].append(trigger)

    def add_conditional_trigger(self, triggers, exp, sequence):
        """Add conditional trigger to a named sequence."""
        if sequence not in self.cond_triggers:
            self.cond_triggers[sequence] = []
        self.cond_triggers[sequence].append([triggers, exp])

    def add_sequence(self, sequence, is_implicit=False):
        """Add a sequence."""
        if sequence not in self.sequences:
            self.sequences.append(sequence)
            if is_implicit:
                self.implicit_sequences.append(sequence)

    def describe(self):
        """Return title and description of the current task."""
        info = {}
        for item in 'title', 'description':
            info[item] = self.rtconfig[item]
        return info

    def check_for_explicit_cycling(self):
        """Check for explicitly somewhere.

        Must be called after all graph sequences added.
        """
        if len(self.sequences) == 0 and self.used_in_offset_trigger:
            raise TaskDefError(
                "No cycling sequences defined for %s" % self.name)

    @classmethod
    def get_cleanup_cutoff_point(cls, my_point, offset_sequence_tuples):
        """Extract the max dependent cycle point for this point."""
        if not offset_sequence_tuples:
            # This task does not have dependent tasks at other cycles.
            return my_point
        cutoff_points = []
        for offset_string, sequence in offset_sequence_tuples:
            if offset_string is None:
                # This indicates a dependency that lasts for the whole run.
                return None
            if sequence is None:
                # This indicates a simple offset interval such as [-PT6H].
                cutoff_points.append(
                    my_point - get_interval(offset_string))
                continue
            # This is a complicated offset like [02T00-P1W].
            dependent_point = sequence.get_start_point()

            matching_dependent_points = []
            while dependent_point is not None:
                # TODO: Is it realistically possible to hang in this loop?
                target_point = (
                    get_point_relative(offset_string, dependent_point))
                if target_point > my_point:
                    # Assume monotonic (target_point can never jump back).
                    break
                if target_point == my_point:
                    # We have found a dependent_point for my_point.
                    matching_dependent_points.append(dependent_point)
                dependent_point = sequence.get_next_point_on_sequence(
                    dependent_point)
            if matching_dependent_points:
                # Choose the largest of the dependent points.
                cutoff_points.append(matching_dependent_points[-1])
        if cutoff_points:
            max_cutoff_point = max(cutoff_points)
            if max_cutoff_point < my_point:
                # This is caused by future triggers - default to my_point.
                return my_point
            return max_cutoff_point
        # There aren't any dependent tasks in other cycles for my_point.
        return my_point

    def update_mean_total_elapsed_time(self, t_started, t_succeeded):
        """Update the mean total elapsed time (all instances of this task)."""
        if not t_started:
            # In case the started messaged did not come in.
            # (TODO - and we don't retain started time on restart?)
            return
        self.elapsed_times.append(t_succeeded - t_started)
        self.mean_total_elapsed_time = (
            sum(self.elapsed_times) / len(self.elapsed_times))

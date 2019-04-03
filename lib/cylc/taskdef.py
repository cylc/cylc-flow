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

"""Task definition."""

from collections import deque

from cylc.cycling.loader import (
    get_point_relative, get_interval, is_offset_absolute)
from cylc.exceptions import TaskDefError
from cylc.task_id import TaskID


class TaskDef(object):
    """Task definition."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = [
        "run_mode", "rtconfig", "start_point",
        "spawn_ahead", "sequences",
        "used_in_offset_trigger", "max_future_prereq_offset",
        "intercycle_offsets", "sequential", "is_coldstart",
        "suite_polling_cfg", "clocktrigger_offset", "expiration_offset",
        "namespace_hierarchy", "dependencies", "outputs", "param_var",
        "external_triggers", "xtrig_labels", "xclock_label",
        "name", "elapsed_times"]

    # Store the elapsed times for a maximum of 10 cycles
    MAX_LEN_ELAPSED_TIMES = 10

    def __init__(self, name, rtcfg, run_mode, start_point, spawn_ahead):
        if not TaskID.is_valid_name(name):
            raise TaskDefError("Illegal task name: %s" % name)

        self.run_mode = run_mode
        self.rtconfig = rtcfg
        self.start_point = start_point
        self.spawn_ahead = spawn_ahead

        self.sequences = []
        self.used_in_offset_trigger = False

        # some defaults
        self.max_future_prereq_offset = None
        self.intercycle_offsets = set([])
        self.sequential = False
        self.suite_polling_cfg = {}

        self.clocktrigger_offset = None
        self.expiration_offset = None
        self.namespace_hierarchy = []
        self.dependencies = {}
        self.outputs = []
        self.param_var = {}
        self.external_triggers = []
        self.xtrig_labels = set()
        self.xclock_label = None
        # Note a task can only have one clock xtrigger - if it depends on
        # several we just keep the label of the one with the largest offset
        # (this is determined and set during suite config parsing, to avoid
        # storing the offset here in the taskdef).

        self.name = name
        self.elapsed_times = deque(maxlen=self.MAX_LEN_ELAPSED_TIMES)

    def add_dependency(self, dependency, sequence):
        """Add a dependency to a named sequence.

        Args:
            dependency (cylc.task_trigger.Dependency): The dependency to add.
            sequence (cylc.cycling.SequenceBase): The sequence for which this
                dependency applies.

        """
        if sequence not in self.dependencies:
            self.dependencies[sequence] = []
        self.dependencies[sequence].append(dependency)

    def add_sequence(self, sequence):
        """Add a sequence."""
        if sequence not in self.sequences:
            self.sequences.append(sequence)

    def describe(self):
        """Return title and description of the current task."""
        return self.rtconfig['meta']

    def check_for_explicit_cycling(self):
        """Check for explicitly somewhere.

        Must be called after all graph sequences added.
        """
        if len(self.sequences) == 0 and self.used_in_offset_trigger:
            raise TaskDefError(
                "No cycling sequences defined for %s" % self.name)

    def get_cleanup_cutoff_point(self, point):
        """Extract the max dependent cycle point for this point."""
        if not self.intercycle_offsets:
            # This task does not have dependent tasks at other cycles.
            return point
        cutoff_points = []
        for offset_string, sequence in self.intercycle_offsets:
            if offset_string is None:
                # This indicates a dependency that lasts for the whole run.
                return None
            if sequence is None:
                # This indicates a simple offset interval such as [-PT6H].
                cutoff_points.append(point - get_interval(offset_string))
                continue
            if is_offset_absolute(offset_string):
                stop_point = sequence.get_stop_point()
                if stop_point:
                    # Stop point of the sequence is a good cutoff point for an
                    # absolute "offset"
                    cutoff_points.append(stop_point)
                    continue
                else:
                    # The dependency lasts for the whole run.
                    return None

            # This is a complicated offset like [02T00-P1W].
            dependent_point = sequence.get_start_point()

            my_cutoff_point = None
            while dependent_point is not None:
                # TODO: Is it realistically possible to hang in this loop?
                target_point = (
                    get_point_relative(offset_string, dependent_point))
                if target_point > point:
                    # Assume monotonic (target_point can never jump back).
                    break
                if target_point == point:
                    # We have found a dependent_point for point.
                    my_cutoff_point = dependent_point
                dependent_point = sequence.get_next_point_on_sequence(
                    dependent_point)
            if my_cutoff_point:
                # Choose the largest of the dependent points.
                cutoff_points.append(my_cutoff_point)
        if cutoff_points:
            max_cutoff_point = max(cutoff_points)
            if max_cutoff_point < point:
                # This is caused by future triggers - default to point.
                return point
            return max_cutoff_point
        # There aren't any dependent tasks in other cycles for point.
        return point

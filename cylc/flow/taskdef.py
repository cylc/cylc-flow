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

from cylc.flow.cycling.loader import (
    get_point_relative, get_interval, is_offset_absolute)
from cylc.flow.exceptions import TaskDefError
from cylc.flow.task_id import TaskID


class TaskDef(object):
    """Task definition."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = [
        "run_mode", "rtconfig", "start_point", "sequences",
        "used_in_offset_trigger", "max_future_prereq_offset",
        "intercycle_offsets", "sequential", "is_coldstart",
        "suite_polling_cfg", "clocktrigger_offset", "expiration_offset",
        "namespace_hierarchy", "dependencies", "downstreams", "outputs", "param_var",
        "external_triggers", "xtrig_labels", "name", "elapsed_times"]

    # Store the elapsed times for a maximum of 10 cycles
    MAX_LEN_ELAPSED_TIMES = 10

    def __init__(self, name, rtcfg, run_mode, start_point):
        if not TaskID.is_valid_name(name):
            raise TaskDefError("Illegal task name: %s" % name)

        self.run_mode = run_mode
        self.rtconfig = rtcfg
        self.start_point = start_point

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
        self.outputs = set()
        self.downstreams = {}  # SoD
        self.param_var = {}
        self.external_triggers = []
        self.xtrig_labels = {}  # {sequence: [labels]}

        self.name = name
        self.elapsed_times = deque(maxlen=self.MAX_LEN_ELAPSED_TIMES)

    def add_downstreams(self, trigger, downstream, sequence):
        """Map task outputs to downstream tasks that depend on them.

          {sequence:
              {
                 output: [(a,o1), (b,o2)]  # (task-name, offset)
              }}
        """
        name = downstream
        offset = trigger.cycle_point_offset
        self.downstreams.setdefault(sequence, {}).setdefault(trigger, []).append((name, offset))

    def add_dependency(self, dependency, sequence):
        """Add a dependency to a named sequence.

        Args:
            dependency (cylc.flow.task_trigger.Dependency): The dependency to
                add.
            sequence (cylc.flow.cycling.SequenceBase): The sequence for which
                this dependency applies.

        """
        self.dependencies.setdefault(sequence, []).append(dependency)

    def add_xtrig_label(self, xtrig_label, sequence):
        """Add an xtrigger to a named sequence.

        Args:
            xtrig_label: The xtrigger label to add.
            sequence (cylc.cycling.SequenceBase): The sequence for which this
                xtrigger applies.

        """
        self.xtrig_labels.setdefault(sequence, []).append(xtrig_label)

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

    def get_parent_points(self, point):
        """Return the cycle points of my parents, at point.

        TODO is SoS "cleanup_cutoff" point still needed?
        ("Extract the max dependent cycle point for this point.")
        ("cycle point beyond which this task can be removed from the pool.")

        """
        # TODO can we avoid this computation sometimes? (where it is used)
        parent_points = set()
        for seq in self.sequences:
            if not seq.is_on_sequence(point):
                continue
            if seq in self.dependencies:
                # task has prereqs in this sequence
                for dep in self.dependencies[seq]:
                   for trig in dep.task_triggers:
                       # (None for no offset)
                       if trig.cycle_point_offset is None:
                          parent_points.add(point)
                       else:
                          parent_points.add(point + get_interval(trig.cycle_point_offset))
        return parent_points

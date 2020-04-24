# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

"""Task definition."""

from collections import deque

from cylc.flow.cycling.loader import get_point
from cylc.flow.exceptions import TaskDefError
from cylc.flow.task_id import TaskID
from cylc.flow import LOG


class TaskDef(object):
    """Task definition."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = [
        "run_mode", "rtconfig", "start_point", "sequences",
        "used_in_offset_trigger", "max_future_prereq_offset",
        "sequential", "is_coldstart",
        "suite_polling_cfg", "clocktrigger_offset", "expiration_offset",
        "namespace_hierarchy", "dependencies", "outputs", "param_var",
        "graph_children",
        "external_triggers", "xtrig_labels", "name", "elapsed_times"]

    # Store the elapsed times for a maximum of 10 cycles
    MAX_LEN_ELAPSED_TIMES = 10
    ERR_PREFIX_TASK_NOT_ON_SEQUENCE = "Invalid cycle point for task: "

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
        self.sequential = False
        self.suite_polling_cfg = {}

        self.clocktrigger_offset = None
        self.expiration_offset = None
        self.namespace_hierarchy = []
        self.dependencies = {}
        self.outputs = set()
        self.graph_children = {}
        # graph_parents not currently used, but might be soon:
        # self.graph_parents = {}
        self.param_var = {}
        self.external_triggers = []
        self.xtrig_labels = {}  # {sequence: [labels]}

        self.name = name
        self.elapsed_times = deque(maxlen=self.MAX_LEN_ELAPSED_TIMES)

    def add_graph_child(self, trigger, taskname, sequence):
        """Record child task instances that depend on my outputs.
          {sequence:
              {
                 output: [(a,t1), (b,t2), ...]  # (task-name, trigger)
              }
          }
        """
        self.graph_children.setdefault(
            sequence, {}).setdefault(
                trigger.output, []).append((taskname, trigger))

    # graph_parents not currently used, but might be soon:
    # def add_graph_parent(self, trigger, parent, sequence):
    #    """Record task instances that I depend on.
    #      {
    #         sequence: set([(a,t1), (b,t2), ...])  # (task-name, trigger)
    #      }
    #    """
    #    if sequence not in self.graph_parents:
    #        self.graph_parents[sequence] = set()
    #    self.graph_parents[sequence].add((parent, trigger))

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
        """Return the cycle points of my parents, at point."""
        parent_points = set()
        for seq in self.sequences:
            if not seq.is_on_sequence(point):
                continue
            if seq in self.dependencies:
                # task has prereqs in this sequence
                for dep in self.dependencies[seq]:
                    if dep.suicide:
                        continue
                    for trig in dep.task_triggers:
                        parent_points.add(trig.get_parent_point(point))
        return parent_points

    def get_abs_triggers(self, point):
        """Return my absolute triggers, if any, at point."""
        abs_triggers = set()
        for seq in self.sequences:
            if not seq.is_on_sequence(point):
                continue
            if seq in self.dependencies:
                # task has prereqs in this sequence
                for dep in self.dependencies[seq]:
                    for trig in dep.task_triggers:
                        if trig.offset_is_absolute or trig.offset_is_from_icp:
                            abs_triggers.add(trig)
        return abs_triggers

    def is_valid_point(self, point):
        """Return True if point is on-sequence and within bounds."""
        for sequence in self.sequences:
            if sequence.is_valid(point):
                return True
        else:
            LOG.warning("%s%s, %s" % (
                self.ERR_PREFIX_TASK_NOT_ON_SEQUENCE, self.name, point))
            return False

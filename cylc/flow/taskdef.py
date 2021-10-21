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

"""Task definition."""

from collections import deque

import cylc.flow.flags
from cylc.flow.exceptions import TaskDefError
from cylc.flow.task_id import TaskID
from cylc.flow.task_state import (
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED
)
from cylc.flow import LOG
from cylc.flow.task_outputs import SORT_ORDERS


def generate_graph_children(tdef, point):
    """Determine graph children of this task (for spawning)."""
    graph_children = {}
    for seq, dout in tdef.graph_children.items():
        for output, downs in dout.items():
            if output not in graph_children:
                graph_children[output] = []
            for name, trigger in downs:
                child_point = trigger.get_child_point(point, seq)
                is_abs = (
                    trigger.offset_is_absolute or
                    trigger.offset_is_from_icp
                )
                if is_abs and trigger.get_parent_point(point) != point:
                    # If 'foo[^] => bar' only spawn off of '^'.
                    continue
                if seq.is_valid(child_point):
                    # E.g.: foo should trigger only on T06:
                    #   PT6H = "waz"
                    #   T06 = "waz[-PT6H] => foo"
                    graph_children[output].append((name, child_point, is_abs))

    if tdef.sequential:
        # Add next-instance child.
        nexts = []
        for seq in tdef.sequences:
            nxt = seq.get_next_point(point)
            if nxt is not None:
                # Within sequence bounds.
                nexts.append(nxt)
        if nexts:
            if TASK_OUTPUT_SUCCEEDED not in graph_children:
                graph_children[TASK_OUTPUT_SUCCEEDED] = []
            graph_children[TASK_OUTPUT_SUCCEEDED].append(
                (tdef.name, min(nexts), False))

    return graph_children


def generate_graph_parents(tdef, point):
    """Determine graph parents of this task."""
    graph_parents = {}
    for seq, ups in tdef.graph_parents.items():
        graph_parents[seq] = []
        for name, trigger in ups:
            parent_point = trigger.get_parent_point(point)
            is_abs = (trigger.offset_is_absolute or
                      trigger.offset_is_from_icp)
            if is_abs and parent_point != point:
                # If 'foo[^] => bar' only spawn off of '^'.
                continue
            if seq.is_valid(parent_point):
                # E.g.: foo should trigger only on T06:
                #   PT6H = "waz"
                #   T06 = "waz[-PT6H] => foo"
                graph_parents[seq].append((name, parent_point, is_abs))

    if tdef.sequential:
        # Add prev-instance parent.
        prevs = []
        for seq in tdef.sequences:
            prev = seq.get_prev_point(point)
            if prev is not None:
                # Within sequence bounds.
                prevs.append(prev)
        if prevs:
            if seq not in graph_parents:
                graph_parents[seq] = []
            graph_parents[seq].append((tdef.name, min(prevs), False))

    return graph_parents


class TaskDef:
    """Task definition."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = [
        "run_mode", "rtconfig", "start_point", "initial_point", "sequences",
        "used_in_offset_trigger", "max_future_prereq_offset",
        "sequential", "is_coldstart",
        "workflow_polling_cfg", "clocktrigger_offset", "expiration_offset",
        "namespace_hierarchy", "dependencies", "outputs", "param_var",
        "graph_children", "graph_parents", "has_abs_triggers",
        "external_triggers", "xtrig_labels", "name", "elapsed_times"]

    # Store the elapsed times for a maximum of 10 cycles
    MAX_LEN_ELAPSED_TIMES = 10
    ERR_PREFIX_TASK_NOT_ON_SEQUENCE = "Invalid cycle point for task: "

    def __init__(self, name, rtcfg, run_mode, start_point, initial_point):
        if not TaskID.is_valid_name(name):
            raise TaskDefError("Illegal task name: %s" % name)

        self.run_mode = run_mode
        self.rtconfig = rtcfg
        self.start_point = start_point
        self.initial_point = initial_point

        self.sequences = []
        self.used_in_offset_trigger = False

        # some defaults
        self.max_future_prereq_offset = None
        self.sequential = False
        self.workflow_polling_cfg = {}

        self.clocktrigger_offset = None
        self.expiration_offset = None
        self.namespace_hierarchy = []
        self.dependencies = {}
        self.outputs = {}  # {output: (message, is_required)}
        self.graph_children = {}
        self.graph_parents = {}
        self.param_var = {}
        self.external_triggers = []
        self.xtrig_labels = {}  # {sequence: [labels]}

        self.name = name
        self.elapsed_times = deque(maxlen=self.MAX_LEN_ELAPSED_TIMES)
        self._add_std_outputs()
        self.has_abs_triggers = False

    def add_output(self, output, message):
        """Add a new task output as defined under [runtime]."""
        # optional/required is None until defined by the graph
        self.outputs[output] = (message, None)

    def _add_std_outputs(self):
        """Add the standard outputs."""
        # optional/required is None until defined by the graph
        for output in SORT_ORDERS:
            self.outputs[output] = (output, None)

    def set_required_output(self, output, required):
        """Set outputs to required or optional."""
        # (Note outputs and associated messages already defined.)
        message, _ = self.outputs[output]
        self.outputs[output] = (message, required)

    def tweak_outputs(self):
        """Output consistency checking and tweaking."""

        # If :succeed or :fail not set, assume success is required.
        # Unless submit (and submit-fail) is optional (don't stall
        # because of missing succeed if submit is optional).
        if (
            self.outputs[TASK_OUTPUT_SUCCEEDED][1] is None
            and self.outputs[TASK_OUTPUT_FAILED][1] is None
            and self.outputs[TASK_OUTPUT_SUBMITTED][1] is not False
            and self.outputs[TASK_OUTPUT_SUBMIT_FAILED][1] is not False
        ):
            self.set_required_output(TASK_OUTPUT_SUCCEEDED, True)

        # In Cylc 7 back compat mode, make all success outputs required.
        if cylc.flow.flags.cylc7_back_compat:
            for output in [
                TASK_OUTPUT_SUBMITTED,
                TASK_OUTPUT_SUCCEEDED
            ]:
                self.set_required_output(output, True)

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
    def add_graph_parent(self, trigger, parent, sequence):
        """Record task instances that I depend on.
          {
             sequence: set([(a,t1), (b,t2), ...])  # (task-name, trigger)
          }
        """
        if sequence not in self.graph_parents:
            self.graph_parents[sequence] = set()
        self.graph_parents[sequence].add((parent, trigger))

    def add_dependency(self, dependency, sequence):
        """Add a dependency to a named sequence.

        Args:
            dependency (cylc.flow.task_trigger.Dependency): The dependency to
                add.
            sequence (cylc.flow.cycling.SequenceBase): The sequence for which
                this dependency applies.

        """
        self.dependencies.setdefault(sequence, []).append(dependency)
        if any(
            trig.offset_is_from_icp or
            trig.offset_is_absolute
            for trig in dependency.task_triggers
        ):
            self.has_abs_triggers = True

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
            if not seq.is_valid(point):
                continue
            if seq in self.dependencies:
                # task has prereqs in this sequence
                for dep in self.dependencies[seq]:
                    if dep.suicide:
                        continue
                    for trig in dep.task_triggers:
                        parent_points.add(trig.get_parent_point(point))
        return parent_points

    def has_only_abs_triggers(self, point):
        """Return whether I have only absolute triggers at point."""
        if not self.has_abs_triggers:
            return False
        # Has abs triggers somewhere, but need to check at point.
        has_abs = False
        for seq in self.sequences:
            if not seq.is_valid(point) or seq not in self.dependencies:
                continue
            for dep in self.dependencies[seq]:
                for trig in dep.task_triggers:
                    if (
                        trig.offset_is_absolute or
                        trig.offset_is_from_icp
                    ):
                        has_abs = True
                    else:
                        return False
        return has_abs

    def is_valid_point(self, point):
        """Return True if point is on-sequence and within bounds."""
        is_valid_point = any(
            sequence.is_valid(point)
            for sequence in self.sequences
        )
        if not is_valid_point:
            LOG.warning("%s%s, %s" % (
                self.ERR_PREFIX_TASK_NOT_ON_SEQUENCE, self.name, point))
        return is_valid_point

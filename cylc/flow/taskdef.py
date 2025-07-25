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
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    NamedTuple,
    Set,
    Tuple,
)

from cylc.flow.exceptions import TaskDefError
import cylc.flow.flags
from cylc.flow.task_id import TaskID
from cylc.flow.task_outputs import (
    SORT_ORDERS,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUCCEEDED,
)

if TYPE_CHECKING:
    from cylc.flow.cycling import (
        PointBase,
        SequenceBase,
    )
    from cylc.flow.task_trigger import (
        Dependency,
        TaskTrigger,
    )


class TaskTuple(NamedTuple):
    name: str
    point: 'PointBase'
    is_abs: bool


def generate_graph_children(
    tdef: 'TaskDef', point: 'PointBase'
) -> Dict[str, List[TaskTuple]]:
    """Determine graph children of this task at point."""
    graph_children: Dict[str, List[TaskTuple]] = {}
    for seq, dout in tdef.graph_children.items():
        for output, downs in dout.items():
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
                    graph_children.setdefault(output, []).append(
                        TaskTuple(name, child_point, is_abs)
                    )

    if tdef.sequential:
        # Add next-instance child.
        nexts = []
        for seq in tdef.sequences:
            nxt = seq.get_next_point(point)
            if nxt is not None:
                # Within sequence bounds.
                nexts.append(nxt)
        if nexts:
            graph_children.setdefault(TASK_OUTPUT_SUCCEEDED, []).append(
                TaskTuple(tdef.name, min(nexts), False)
            )

    return graph_children


def generate_graph_parents(
    tdef: 'TaskDef', point: 'PointBase', taskdefs: Dict[str, 'TaskDef']
) -> Dict['SequenceBase', List[TaskTuple]]:
    """Determine concrete graph parents of task tdef at point.

    Infer parents by reversing upstream triggers that lead to point/task.
    """
    graph_parents: Dict['SequenceBase', List[TaskTuple]] = {}

    for seq, triggers in tdef.graph_parents.items():
        if not seq.is_valid(point):
            # Don't infer parents if the trigger belongs to a sequence that
            # does not include the child point. E.g.:
            #   T06 = "waz[-PT6H] => foo"
            # here waz[-PT6H] is a parent of T06/foo but not of T12/foo.
            continue
        graph_parents[seq] = []
        for parent_name, trigger in triggers:
            parent_point = trigger.get_parent_point(point)
            if (
                parent_point != point and
                not taskdefs[parent_name].is_valid_point(parent_point)
            ):
                # Don't infer inter-cycle parents if the upstream point is
                # not valid for the parent (which depends on its sequences).
                # NOTE this includes pre-initial dependence where the offset
                # extends back beyond the initial point AND erroneous offsets
                # when different tasks are involved, e.g.:
                #   woo[-Px] => foo
                # where (point -Px) does not land on a valid point for woo.
                # TODO ideally validation would flag this as an error.
                continue
            is_abs = trigger.offset_is_absolute or trigger.offset_is_from_icp
            graph_parents[seq].append(
                TaskTuple(parent_name, parent_point, is_abs)
            )

    if tdef.sequential:
        # Add implicit previous-instance parent.
        prevs = []
        for seq in tdef.sequences:
            prev = seq.get_prev_point(point)
            if prev is not None:
                # Within sequence bounds.
                prevs.append(prev)
        if prevs:
            graph_parents.setdefault(seq, []).append(
                TaskTuple(tdef.name, min(prevs), False)
            )

    return graph_parents


class TaskDef:
    """Task definition."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = [
        "rtconfig", "start_point", "initial_point", "sequences",
        "used_in_offset_trigger", "max_future_prereq_offset",
        "sequential", "is_coldstart",
        "workflow_polling_cfg", "expiration_offset",
        "namespace_hierarchy", "dependencies", "outputs", "param_var",
        "graph_children", "graph_parents", "has_abs_triggers",
        "external_triggers", "xtrig_labels", "name", "elapsed_times"]

    # Store the elapsed times for a maximum of 10 cycles
    MAX_LEN_ELAPSED_TIMES = 10

    def __init__(self, name, rtcfg, start_point, initial_point):
        if not TaskID.is_valid_name(name):
            raise TaskDefError("Illegal task name: %s" % name)
        self.name: str = name
        self.rtconfig = rtcfg
        self.start_point = start_point
        self.initial_point = initial_point

        self.sequences: List[SequenceBase] = []
        self.used_in_offset_trigger = False

        # some defaults
        self.max_future_prereq_offset = None
        self.sequential = False
        self.workflow_polling_cfg = {}

        self.expiration_offset = None
        self.namespace_hierarchy = []
        self.dependencies: Dict[SequenceBase, List[Dependency]] = {}
        self.outputs = {}  # {output: (message, is_required)}
        self.graph_children: Dict[
            SequenceBase, Dict[str, Set[Tuple[str, TaskTrigger]]]
        ] = {}
        self.graph_parents: Dict[
            SequenceBase, Set[Tuple[str, TaskTrigger]]
        ] = {}
        self.param_var = {}
        self.external_triggers = []
        self.xtrig_labels = {}  # {sequence: [labels]}

        self.elapsed_times = deque(maxlen=self.MAX_LEN_ELAPSED_TIMES)
        self._add_std_outputs()
        self.has_abs_triggers = False

    def add_output(self, output, message):
        """Add a new task output as defined under [runtime]."""
        # optional/required is None until defined by the graph
        self.outputs[output] = (message, None)

    def get_output(self, message):
        """Return output name corresponding to task message."""
        for name, (msg, _) in self.outputs.items():
            if msg == message:
                return name
        raise KeyError(f"Unknown task output message: {message}")

    def _add_std_outputs(self):
        """Add the standard outputs."""
        # optional/required is None until defined by the graph
        for output in SORT_ORDERS:
            self.outputs[output] = (output, None)

    def set_required_output(self, output, required):
        """Set outputs to required or optional."""
        # (Note outputs and associated messages are already defined.)
        message, _ = self.outputs[output]
        self.outputs[output] = (message, required)

    def tweak_outputs(self):
        """Output consistency checking and tweaking."""
        # If :succeed or :fail not set, assume success is required.
        if (
            self.outputs[TASK_OUTPUT_SUCCEEDED][1] is None
            and self.outputs[TASK_OUTPUT_FAILED][1] is None
        ):
            self.set_required_output(TASK_OUTPUT_SUCCEEDED, True)

        # In Cylc 7 back compat mode, make all success outputs required.
        if cylc.flow.flags.cylc7_back_compat:
            for output in [
                TASK_OUTPUT_SUBMITTED,
                TASK_OUTPUT_SUCCEEDED
            ]:
                self.set_required_output(output, True)

    def add_graph_child(
        self, trigger: 'TaskTrigger', taskname: str, sequence: 'SequenceBase'
    ) -> None:
        """Record child task instances that depend on my outputs.
          {sequence:
              {
                 output: [(a,t1), (b,t2), ...]  # (task-name, trigger)
              }
          }
        """
        self.graph_children.setdefault(
            sequence, {}
        ).setdefault(
            trigger.output, set()
        ).add((taskname, trigger))

    def add_graph_parent(
        self, trigger: 'TaskTrigger', parent: str, sequence: 'SequenceBase'
    ) -> None:
        """Record task instances that I depend on.
          {
             sequence: set([(a,t1), (b,t2), ...])  # (task-name, trigger)
          }
        """
        self.graph_parents.setdefault(sequence, set()).add((parent, trigger))

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

    def get_prereqs(self, point):
        """Return my prereqs, at point."""
        prereqs = set()
        for seq in self.sequences:
            if not seq.is_valid(point):
                continue
            if seq in self.dependencies:
                # task has prereqs in this sequence
                for dep in self.dependencies[seq]:
                    if dep.suicide:
                        continue
                    prereqs.add(dep.get_prerequisite(point, self))
        return prereqs

    def get_xtrigs(self, point):
        """Return my xtrigger labels, at point."""
        xlabels = set()
        for seq in self.sequences:
            if not seq.is_valid(point):
                continue
            if seq in self.xtrig_labels:
                # task has xtriggers in this sequence
                xlabels.update(self.xtrig_labels[seq])
        return xlabels

    def get_triggers(self, point):
        """Return my triggers, at point."""
        triggers = set()
        for seq in self.sequences:
            if not seq.is_valid(point):
                continue
            if seq in self.dependencies:
                # task has prereqs in this sequence
                for dep in self.dependencies[seq]:
                    if dep.suicide:
                        continue
                    for trig in dep.task_triggers:
                        triggers.add(trig)
        return triggers

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
                        trig.offset_is_from_icp or
                        # Don't count suicide as a normal trigger:
                        dep.suicide
                    ):
                        has_abs = True
                    else:
                        return False
        return has_abs

    def is_valid_point(self, point: 'PointBase') -> bool:
        """Return True if point is on-sequence and within bounds."""
        return any(
            sequence.is_valid(point) for sequence in self.sequences
        )

    def first_point(self, icp):
        """Return the first point for this task."""
        point = None
        adjusted = []
        for seq in self.sequences:
            pt = seq.get_first_point(icp)
            if pt:
                # may be None if beyond the sequence bounds
                adjusted.append(pt)
        if adjusted:
            point = min(adjusted)
        return point

    def next_point(self, point):
        """Return the next cycle point after point."""
        p_next = None
        adjusted = []
        for seq in self.sequences:
            nxt = seq.get_next_point(point)
            if nxt:
                # may be None if beyond the sequence bounds
                adjusted.append(nxt)
        if adjusted:
            p_next = min(adjusted)
        return p_next

    def is_parentless(self, point):
        """Return True if task has no parents at point.

        Tasks are considered parentless if they have:
          - no parents at all
          - all parents < initial cycle point
          - only absolute triggers

        Absolute-triggered tasks are auto-spawned like true parentless tasks,
        (once the trigger is satisfied they are effectively parentless) but
        with a prerequisite that gets satisfied when the absolute output is
        completed at runtime.
        """
        if not self.graph_parents:
            # No parents at any point
            return True
        if self.sequential:
            # Implicit parents
            return False
        parent_points = self.get_parent_points(point)
        return (
            not parent_points
            or all(x < self.start_point for x in parent_points)
            or self.has_only_abs_triggers(point)
        )

    def __repr__(self) -> str:
        """
        >>> TaskDef(
        ...     name='oliver', rtcfg={}, start_point='1',
        ...     initial_point='1'
        ... )
        <TaskDef 'oliver'>
        """
        return f"<TaskDef '{self.name}'>"

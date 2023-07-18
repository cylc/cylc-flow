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

from cylc.flow.cycling.loader import (
    get_point, get_point_relative, get_interval)
from cylc.flow.prerequisite import Prerequisite
from cylc.flow.task_qualifiers import ALT_QUALIFIERS

# Task trigger names (e.g. foo:fail => bar).
# Can use "foo:fail => bar" or "foo:failed => bar", etc.


class TaskTrigger:
    """Class representing an upstream dependency.

    Args:
        task_name (str): The name of the upstream task.
        cycle_point_offset (str): String representing the offset of the
            upstream task (e.g. -P1D) if this dependency is not an absolute
            one. Else None.
        output (str): The task state / output for this trigger e.g. succeeded.

    """

    __slots__ = ['task_name', 'cycle_point_offset', 'output',
                 'offset_is_irregular', 'offset_is_absolute',
                 'offset_is_from_icp', 'initial_point']

    def __init__(self, task_name, cycle_point_offset, output,
                 offset_is_irregular=False, offset_is_absolute=False,
                 offset_is_from_icp=False, initial_point=None):
        self.task_name = task_name
        self.cycle_point_offset = cycle_point_offset
        self.output = output
        self.offset_is_irregular = offset_is_irregular
        self.offset_is_from_icp = offset_is_from_icp
        self.offset_is_absolute = offset_is_absolute
        self.initial_point = initial_point
        # NEED TO DISTINGUISH BETWEEN ABSOLUTE OFFSETS
        #   2000, 20000101T0600Z, 2000-01-01T06:00+00:00, ...
        # AND NON-ABSOLUTE IRREGULAR:
        #   -PT6H+P1D, T00, ...
        if (self.offset_is_irregular and any(
                self.cycle_point_offset.startswith(c)
                for c in ['P', '+', '-', 'T'])):
            self.offset_is_absolute = False

    def get_parent_point(self, from_point):
        """Return the specific parent point of this trigger.

        Args:
            from_point (cylc.flow.cycling.PointBase): parent task point.

        Returns:
            cylc.flow.cycling.PointBase: cycle point of the child.

        """
        if self.cycle_point_offset is None:
            point = from_point
        elif self.offset_is_absolute:
            point = get_point(self.cycle_point_offset).standardise()
        else:
            if self.offset_is_from_icp:
                from_point = self.initial_point
            # works with offset_is_irregular or not:
            point = get_point_relative(self.cycle_point_offset, from_point)
        return point

    def get_child_point(self, from_point, seq):
        """Return the specific child task point of this trigger.

        Args:
            from_point (cylc.flow.cycling.PointBase): base point.
            seq: the cycling sequence to find the child point.

        Returns:
            cylc.flow.cycling.PointBase: cycle point of the child.

        """
        if self.cycle_point_offset is None:
            point = from_point
        elif self.offset_is_absolute or self.offset_is_from_icp:
            # First child is at start of sequence.
            #   E.g. for "R/1/P1 = foo[2] => bar"
            # foo.2 should spawn bar.1; then we auto-spawn bar.2,3,...
            point = seq.get_start_point()
        elif self.offset_is_irregular:
            # Change offset sign to find children
            #   e.g. -P1D+PT18H to +P1D-PT18H
            point = get_point_relative(
                self.cycle_point_offset.translate(
                    self.cycle_point_offset.maketrans('-+', '+-')), from_point)
        else:
            point = from_point - get_interval(self.cycle_point_offset)
        return point

    def get_point(self, point):
        """Return the point of the output to which this TaskTrigger pertains.

        Args:
            point (cylc.flow.cycling.PointBase): cycle point of dependent task.

        Returns:
            cylc.flow.cycling.PointBase: cycle point of the dependency.

        """
        if self.offset_is_absolute:
            point = get_point(self.cycle_point_offset).standardise()
        elif self.offset_is_from_icp:
            point = get_point_relative(
                self.cycle_point_offset, self.initial_point)
        elif self.cycle_point_offset:
            point = get_point_relative(self.cycle_point_offset, point)
        return point

    def __str__(self):
        if not self.offset_is_irregular and self.offset_is_absolute:
            point = get_point(self.cycle_point_offset).standardise()
            return '%s[%s]:%s' % (self.task_name, point, self.output)
        elif self.cycle_point_offset:
            return '%s[%s]:%s' % (self.task_name, self.cycle_point_offset,
                                  self.output)
        else:
            return '%s:%s' % (self.task_name, self.output)

    __repr__ = __str__

    @staticmethod
    def standardise_name(name):
        """Replace trigger name aliases with standard names.

        Arg name should be a valid standard name or alias, otherwise assumed
        to be a custom trigger and return as-is.

        Examples:
            >>> TaskTrigger.standardise_name('foo')
            'foo'
            >>> TaskTrigger.standardise_name('succeed')
            'succeeded'
            >>> TaskTrigger.standardise_name('succeeded')
            'succeeded'

        """
        return ALT_QUALIFIERS.get(name, name)


class Dependency:
    """A graph dependency in its abstract form.

    Used to generate cylc.flow.prerequisite.Prerequisite objects.

    Args:
        exp (list): A (nested) list of TaskTrigger objects and conditional
            characters representing the dependency. E.G: "foo & bar" would be
            [<TaskTrigger("foo")>, "&", <TaskTrigger("Bar")>].
        task_triggers (set): A set of TaskTrigger objects contained in the
            expression (exp).
        suicide (bool): True if this is a suicide trigger else False.

    """

    __slots__ = ['_exp', 'task_triggers', 'suicide']

    def __init__(self, exp, task_triggers, suicide):
        self._exp = exp
        self.task_triggers = tuple(task_triggers)  # More memory efficient.
        self.suicide = suicide

    def get_prerequisite(self, point, tdef):
        """Generate a Prerequisite object from this dependency.

        Args:
            point (cylc.flow.cycling.PointBase): The cycle point at which to
                generate the Prerequisite for.
            tdef (cylc.flow.taskdef.TaskDef): The TaskDef of the dependent
                task.

        Returns:
            cylc.flow.prerequisite.Prerequisite

        """
        # Create Prerequisite.
        cpre = Prerequisite(point)

        # Loop over TaskTrigger instances.
        for task_trigger in self.task_triggers:
            if task_trigger.cycle_point_offset is not None:
                # Compute trigger cycle point from offset.
                if task_trigger.offset_is_from_icp:
                    prereq_offset_point = get_point_relative(
                        task_trigger.cycle_point_offset, tdef.initial_point)
                else:
                    prereq_offset_point = get_point_relative(
                        task_trigger.cycle_point_offset, point)
                if prereq_offset_point > point:
                    # Update tdef.max_future_prereq_offset.
                    prereq_offset = prereq_offset_point - point
                    if (tdef.max_future_prereq_offset is None or
                            (prereq_offset >
                             tdef.max_future_prereq_offset)):
                        tdef.max_future_prereq_offset = (
                            prereq_offset)
                cpre.add(
                    task_trigger.task_name,
                    task_trigger.get_point(point),
                    task_trigger.output,
                    (
                        (prereq_offset_point < tdef.start_point) &
                        (point >= tdef.start_point)
                    )
                )
            else:
                # Trigger is within the same cycle point.
                # Register task message with Prerequisite object.
                cpre.add(task_trigger.task_name,
                         task_trigger.get_point(point),
                         task_trigger.output)
        cpre.set_condition(self.get_expression(point))
        return cpre

    def get_expression(self, point):
        """Return the expression as a string.

        Args:
            point (cylc.flow.cycling.PointBase): The cycle point at which to
                generate the expression string for.

        Return:
            string: The expression as a parsable string in the cylc graph
            format.

        """
        return ''.join(self._stringify_list(self._exp, point))

    def __str__(self):
        ret = []
        if self.suicide:
            ret.append('!')
        for item in self._exp:
            if isinstance(item, list):
                ret.append(str(item))
            else:
                ret.append('( %s )' % str(item))
        return ' '.join(ret)

    @classmethod
    def _stringify_list(cls, nested_expr, point):
        """Stringify a nested list of TaskTrigger objects."""
        ret = []
        for item in nested_expr:
            if isinstance(item, TaskTrigger):
                ret.append(
                    Prerequisite.MESSAGE_TEMPLATE % (
                        item.get_point(point),
                        item.task_name,
                        item.output,
                    )
                )
            elif isinstance(item, list):
                ret.extend(['('] + cls._stringify_list(item, point) + [')'])
            else:
                ret.append(item)
        return ret

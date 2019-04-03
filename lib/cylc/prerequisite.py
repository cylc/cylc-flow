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

"""Functionality for expressing and evaluating logical triggers."""

import math

from cylc.conditional_simplifier import ConditionalSimplifier
from cylc.cycling.loader import get_point
from cylc.exceptions import TriggerExpressionError


class Prerequisite(object):
    """The concrete result of an abstract logical trigger expression."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["satisfied", "_all_satisfied",
                 "target_point_strings", "start_point",
                 "pre_initial_messages", "conditional_expression", "point"]

    # Extracts T from "foo.T succeeded" etc.
    SATISFIED_TEMPLATE = 'bool(self.satisfied[("%s", "%s", "%s")])'
    MESSAGE_TEMPLATE = '%s.%s %s'

    DEP_STATE_SATISFIED = 'satisfied naturally'
    DEP_STATE_OVERRIDDEN = 'force satisfied'
    DEP_STATE_UNSATISFIED = False

    def __init__(self, point, start_point=None):
        # The cycle point to which this prerequisite belongs.
        # cylc.cycling.PointBase
        self.point = point

        # Start point for prerequisite validity.
        # cylc.cycling.PointBase
        self.start_point = start_point

        # List of cycle point strings that this prerequisite depends on.
        self.target_point_strings = []

        # Dictionary of messages pertaining to this prerequisite.
        # {('task name', 'point string', 'output'): DEP_STATE_X, ...}
        self.satisfied = {}

        # Messages pertaining to pre-initial dependencies.
        # ['task name', 'point string' ,'output']
        self.pre_initial_messages = []

        # Expression present only when conditions are used.
        # 'foo.1 failed & bar.1 succeeded'
        self.conditional_expression = None

        # The cached state of this prerequisite:
        # * `None` (no cached state)
        # * `True` (prerequisite satisfied)
        # * `False` (prerequisite unsatisfied).
        self._all_satisfied = None

    def add(self, name, point, output, pre_initial=False):
        """Register an output with this prerequisite.

        Args:
            name (str): The name of the task to which the output pertains.
            point (str/cylc.cycling.PointBase): The cycle point at which this
                dependent output should appear.
            output (str): String representing the output e.g. "succeeded".
            pre_initial (bool): Set this output as a pre-initial dependency.

        """
        message = (name, str(point), output)

        # Add a new prerequisite message in an UNSATISFIED state.
        self.satisfied[message] = self.DEP_STATE_UNSATISFIED
        if self._all_satisfied is not None:
            self._all_satisfied = False
        if point and str(point) not in self.target_point_strings:
            self.target_point_strings.append(str(point))
        if pre_initial and message not in self.pre_initial_messages:
            self.pre_initial_messages.append(message)

    def get_raw_conditional_expression(self):
        """Return a representation of this prereq as a string.

        Returns None if this prerequisite is not a conditional one.

        """
        expr = self.conditional_expression
        if not expr:
            return None
        for message in self.satisfied:
            expr = expr.replace(self.SATISFIED_TEMPLATE % message,
                                self.MESSAGE_TEMPLATE % message)
        return expr

    def set_condition(self, expr):
        """Set the conditional expression for this prerequisite.

        Resets the cached state (self._all_satisfied).

        """

        drop_these = []
        self._all_satisfied = None

        if self.pre_initial_messages:
            for message in self.pre_initial_messages:
                drop_these.append(message)

        # Needed to drop pre warm-start dependence:
        for message in self.satisfied:
            if message in drop_these:
                continue
            if self.start_point:
                if message[1]:  # Cycle point.
                    if (get_point(message[1]) < self.start_point and
                            self.point >= self.start_point):
                        # Drop if outside of relevant point range.
                        drop_these.append(message)

        for message in drop_these:
            if message in self.satisfied:
                self.satisfied.pop(message)

        if '|' in expr:
            if drop_these:
                simpler = ConditionalSimplifier(
                    expr, [self.MESSAGE_TEMPLATE % m for m in drop_these])
                expr = simpler.get_cleaned()
            # Make a Python expression so we can eval() the logic.
            for message in self.satisfied:
                expr = expr.replace(self.MESSAGE_TEMPLATE % message,
                                    self.SATISFIED_TEMPLATE % message)
            self.conditional_expression = expr

    def is_satisfied(self):
        """Return True if prerequisite is satisfied.

        Return cached state if present, else evaluate the prerequisite.

        """
        if self._all_satisfied is not None:
            return self._all_satisfied
        else:
            # No cached value.
            if not self.satisfied:
                # No prerequisites left after pre-initial simplification.
                return True
            if self.conditional_expression:
                # Trigger expression with at least one '|': use eval.
                self._all_satisfied = self._conditional_is_satisfied()
            else:
                self._all_satisfied = all(self.satisfied.values())
            return self._all_satisfied

    def _conditional_is_satisfied(self):
        """Evaluate the prerequisite's condition expression.

        Does not cache the result.

        """
        try:
            res = eval(self.conditional_expression)
        except (SyntaxError, ValueError) as exc:
            err_msg = str(exc)
            if str(exc).find("unexpected EOF") != -1:
                err_msg += (
                    " (could be unmatched parentheses in the graph string?)")
            raise TriggerExpressionError(
                '"%s":\n%s' % (self.get_raw_conditional_expression(), err_msg))
        return res

    def satisfy_me(self, all_task_outputs):
        """Evaluate pre-requisite against known outputs.

        Updates cache with the evaluation result.

        """
        relevant_messages = all_task_outputs & set(self.satisfied)
        for message in relevant_messages:
            self.satisfied[message] = self.DEP_STATE_SATISFIED
            if self.conditional_expression is None:
                self._all_satisfied = all(self.satisfied.values())
            else:
                self._all_satisfied = self._conditional_is_satisfied()
        return relevant_messages

    def dump(self):
        """ Return an array of strings representing each message and its state.
        """
        res = []
        if self.conditional_expression:
            temp = self.get_raw_conditional_expression()
            messages = []
            num_length = int(math.ceil(float(len(self.satisfied)) / float(10)))
            for ind, message_tuple in enumerate(sorted(self.satisfied)):
                message = self.MESSAGE_TEMPLATE % message_tuple
                char = '%.{0}d'.format(num_length) % ind
                messages.append(['\t%s = %s' % (char, message),
                                 bool(self.satisfied[message_tuple])])
                temp = temp.replace(message, char)
            temp = temp.replace('|', ' | ')
            temp = temp.replace('&', ' & ')
            res.append([temp, self.is_satisfied()])
            res.extend(messages)
        elif self.satisfied:
            for message, val in self.satisfied.items():
                res.append([self.MESSAGE_TEMPLATE % message, val])
        # (Else trigger wiped out by pre-initial simplification.)
        return res

    def set_satisfied(self):
        """Force this prerequisite into the satisfied state.

        State can be overridden by calling `self.satisfy_me`.

        """
        for message in self.satisfied:
            if not self.satisfied[message]:
                self.satisfied[message] = self.DEP_STATE_OVERRIDDEN
        if self.conditional_expression is None:
            self._all_satisfied = True
        else:
            self._all_satisfied = self._conditional_is_satisfied()

    def set_not_satisfied(self):
        """Force this prerequiste into the un-satisfied state.

        State can be overridden by calling `self.satisfy_me`.

        """
        for message in self.satisfied:
            self.satisfied[message] = self.DEP_STATE_UNSATISFIED
        if not self.satisfied:
            self._all_satisfied = True
        elif self.conditional_expression is None:
            self._all_satisfied = False
        else:
            self._all_satisfied = self._conditional_is_satisfied()

    def get_target_points(self):
        """Return a list of cycle points target by each prerequisite,
        including each component of conditionals."""
        return [get_point(p) for p in self.target_point_strings]

    def get_resolved_dependencies(self):
        """Return a list of satisfied dependencies.

        E.G: ['foo.1', 'bar.2']

        """
        return ['%s.%s' % (name, point) for
                (name, point, _), satisfied in self.satisfied.items() if
                satisfied == self.DEP_STATE_SATISFIED]

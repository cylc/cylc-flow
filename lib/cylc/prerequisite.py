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

import math
import re

from cylc.conditional_simplifier import ConditionalSimplifier
from cylc.cycling.loader import get_point
from cylc.suite_logging import ERR


"""A task prerequisite.

The concrete result of an abstract logical trigger expression.

"""


class TriggerExpressionError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class Prerequisite(object):

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["CYCLE_POINT_RE", "SATISFIED_TEMPLATE",
                 "satisfied", "all_satisfied",
                 "target_point_strings", "start_point",
                 "pre_initial_messages", "conditional_expression", "point"]

    # Extracts T from "foo.T succeeded" etc.
    CYCLE_POINT_RE = re.compile('^\w+\.(\S+) .*$')
    SATISFIED_TEMPLATE = 'bool(self.satisfied["%s"])'

    DEP_STATE_SATISFIED = 'satisfied naturally'
    DEP_STATE_OVERRIDDEN = 'force satisfied'
    DEP_STATE_UNSATISFIED = False

    def __init__(self, point, start_point=None):
        self.point = point
        self.satisfied = {}    # satisfied[ label ] = DEP_STATE_X
        self.target_point_strings = []   # list of target cycle points
        self.start_point = start_point
        self.pre_initial_messages = []
        self.conditional_expression = None

    def add(self, message, pre_initial=False):
        # Add a new prerequisite message in an UNSATISFIED state.
        self.satisfied[message] = self.DEP_STATE_UNSATISFIED
        if hasattr(self, 'all_satisfied'):
            self.all_satisfied = False
        match = self.__class__.CYCLE_POINT_RE.match(message)
        if match:
            self.target_point_strings.append(match.groups()[0])
        if pre_initial and message not in pre_initial:
            self.pre_initial_messages.append(message)

    def get_not_satisfied_list(self):
        not_satisfied = []
        for message in self.satisfied:
            if not self.satisfied[message]:
                not_satisfied.append(message)
        return not_satisfied

    def get_raw_conditional_expression(self):
        expr = self.conditional_expression
        for message in self.satisfied:
            expr = expr.replace(self.SATISFIED_TEMPLATE % message, message)
        return expr

    def set_condition(self, expr):
        # 'foo | bar & baz'
        # 'foo:fail | foo'
        # 'foo[T-6]:out1 | baz'

        drop_these = []
        if hasattr(self, 'all_satisfied'):
            delattr(self, 'all_satisfied')

        if self.pre_initial_messages:
            for message in self.pre_initial_messages:
                drop_these.append(message)

        # Needed to drop pre warm-start dependence:
        for message in self.satisfied:
            if message in drop_these:
                continue
            if self.start_point:
                # Extract the cycle point from the message.
                match = self.CYCLE_POINT_RE.search(message)
                if match:
                    # Get cycle point
                    if (get_point(match.groups()[0]) < self.start_point and
                            self.point >= self.start_point):
                        # Drop if outside of relevant point range.
                        drop_these.append(message)

        for message in drop_these:
            if message in self.satisfied:
                self.satisfied.pop(message)

        if '|' in expr:
            if drop_these:
                simpler = ConditionalSimplifier(expr, drop_these)
                expr = simpler.get_cleaned()
            # Make a Python expression so we can eval() the logic.
            for message in self.satisfied:
                expr = expr.replace(message, self.SATISFIED_TEMPLATE % message)
            self.conditional_expression = expr

    def is_satisfied(self):
        try:
            return self.all_satisfied
        except AttributeError:
            # No cached value.
            if not self.satisfied:
                # No prerequisites left after pre-initial simplification.
                return True
            if self.conditional_expression:
                # Trigger expression with at least one '|': use eval.
                self.all_satisfied = self._conditional_is_satisfied()
            else:
                self.all_satisfied = all(self.satisfied.values())
            return self.all_satisfied

    def _conditional_is_satisfied(self):
        try:
            res = eval(self.conditional_expression)
        except Exception, exc:
            err_msg = str(exc)
            if str(exc).find("unexpected EOF") != -1:
                err_msg += ("\n(?could be unmatched parentheses in the graph "
                            "string?)")
            ERR.error(err_msg)
            raise TriggerExpressionError(
                '"' + self.get_raw_conditional_expression() + '"')
        return res

    def satisfy_me(self, output_msgs, outputs):
        """Can any completed outputs satisfy any of my prequisites?

        This needs to be fast as it's called for all unsatisfied tasks
        whenever there's a change.

        At the moment, this uses set intersections to filter out
        irrelevant outputs - using for loops and if matching is very
        slow.

        """
        relevant_msgs = output_msgs & set(self.satisfied)
        for msg in relevant_msgs:
            for message in self.satisfied:
                if message == msg:
                    self.satisfied[message] = self.DEP_STATE_SATISFIED
            if self.conditional_expression is None:
                self.all_satisfied = all(self.satisfied.values())
            else:
                self.all_satisfied = self._conditional_is_satisfied()
        return relevant_msgs

    def dump(self):
        """ Return an array of strings representing each message and its state.
        """
        res = []
        if self.conditional_expression:
            temp = self.get_raw_conditional_expression()
            messages = []
            num_length = int(math.ceil(float(len(self.satisfied)) / float(10)))
            for ind, message in enumerate(sorted(self.satisfied)):
                char = '%.{0}d'.format(num_length) % ind
                messages.append(['\t%s = %s' % (char, message),
                                self.satisfied[message]])
                temp = temp.replace(message, char)
            temp = temp.replace('|', ' | ')
            temp = temp.replace('&', ' & ')
            res.append([temp, self.is_satisfied()])
            res.extend(messages)
        elif self.satisfied:
            for message, val in self.satisfied.items():
                res.append([message, val])
        # (Else trigger wiped out by pre-initial simplification.)
        return res

    def set_satisfied(self):
        for message in self.satisfied:
            if not self.satisfied[message]:
                self.satisfied[message] = self.DEP_STATE_OVERRIDDEN
        if self.conditional_expression is None:
            self.all_satisfied = True
        else:
            self.all_satisfied = self._conditional_is_satisfied()

    def set_not_satisfied(self):
        for message in self.satisfied:
            self.satisfied[message] = self.DEP_STATE_UNSATISFIED
        if not self.satisfied:
            self.all_satisfied = True
        elif self.conditional_expression is None:
            self.all_satisfied = False
        else:
            self.all_satisfied = self._conditional_is_satisfied()

    def get_target_points(self):
        """Return a list of cycle points target by each prerequisite,
        including each component of conditionals."""
        return [get_point(p) for p in self.target_point_strings]

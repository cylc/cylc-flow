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

import re
import sys
from cylc.conditional_simplifier import ConditionalSimplifier
from cylc.cycling.loader import get_point
from cylc.suite_logging import ERR
from cylc.task_id import TaskID


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
    __slots__ = ["CYCLE_POINT_RE", "owner_id", "labels", "messages",
                 "messages_set", "satisfied", "all_satisfied", "satisfied_by",
                 "target_point_strings", "start_point",
                 "pre_initial_messages", "conditional_expression",
                 "raw_conditional_expression", "point"]

    # Extracts T from "foo.T succeeded" etc.
    CYCLE_POINT_RE = re.compile('^\w+\.(\S+) .*$')

    def __init__(self, owner_id, point, start_point=None):
        self.point = point
        self.owner_id = owner_id
        self.labels = {}   # labels[ message ] = label
        self.messages = {}   # messages[ label ] = message
        self.messages_set = set()  # = set(self.messages.values())
        self.satisfied = {}    # satisfied[ label ] = True/False
        self.satisfied_by = {}   # self.satisfied_by[ label ] = task_id
        self.target_point_strings = []   # list of target cycle points
        self.start_point = start_point
        self.pre_initial_messages = []
        self.conditional_expression = None
        self.raw_conditional_expression = None

    def add(self, message, label, pre_initial=False):
        # Add a new prerequisite message in an UNSATISFIED state.
        self.messages[label] = message
        self.messages_set.add(message)
        self.labels[message] = label
        self.satisfied[label] = False
        if hasattr(self, 'all_satisfied'):
            self.all_satisfied = False
        m = re.match(self.__class__.CYCLE_POINT_RE, message)
        if m:
            self.target_point_strings.append(m.groups()[0])
        if pre_initial:
            self.pre_initial_messages.append(label)

    def get_not_satisfied_list(self):
        not_satisfied = []
        for label in self.satisfied:
            if not self.satisfied[label]:
                not_satisfied.append(label)
        return not_satisfied

    def set_condition(self, expr):
        # 'foo | bar & baz'
        # 'foo:fail | foo'
        # 'foo[T-6]:out1 | baz'

        drop_these = []
        if hasattr(self, 'all_satisfied'):
            delattr(self, 'all_satisfied')

        if self.pre_initial_messages:
            for k in self.pre_initial_messages:
                drop_these.append(k)

        # Needed to drop pre warm-start dependence:
        for k in self.messages:
            if k in drop_these:
                continue
            if self.start_point:
                m = re.search(
                    r'(' + TaskID.NAME_RE + ')\.(' +
                    TaskID.POINT_RE + ') ', self.messages[k])
                if m:
                    try:
                        foo = m.group().split(".")[1].rstrip()
                        if (get_point(foo) < self.start_point and
                           self.point >= self.start_point):
                            drop_these.append(k)
                    except IndexError:
                        pass

        for label in drop_these:
            if self.messages.get(label):
                msg = self.messages[label]
                self.messages.pop(label)
                self.messages_set.remove(msg)
                self.satisfied.pop(label)
                self.labels.pop(msg)

        if '|' in expr:
            if drop_these:
                simpler = ConditionalSimplifier(expr, drop_these)
                expr = simpler.get_cleaned()
            # Make a Python expression so we can eval() the logic.
            self.raw_conditional_expression = expr
            for label in self.messages:
                expr = re.sub(
                    r'\b' + label + r'\b', 'self.satisfied[\'' + label + '\']',
                    expr)
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
                '"' + self.raw_conditional_expression + '"')
        return res

    def satisfy_me(self, output_msgs, outputs):
        """Can any completed outputs satisfy any of my prequisites?

        This needs to be fast as it's called for all unsatisfied tasks
        whenever there's a change.

        At the moment, this uses set intersections to filter out
        irrelevant outputs - using for loops and if matching is very
        slow.

        """
        relevant_msgs = output_msgs & self.messages_set
        for msg in relevant_msgs:
            for label in self.satisfied:
                if self.messages[label] == msg:
                    self.satisfied[label] = True
                    self.satisfied_by[label] = outputs[msg]  # owner_id
            if self.conditional_expression is None:
                self.all_satisfied = all(self.satisfied.values())
            else:
                self.all_satisfied = self._conditional_is_satisfied()
        return relevant_msgs

    def dump(self):
        # TODO - CHECK THIS WORKS NOW
        # return an array of strings representing each message and its state
        res = []
        if self.raw_conditional_expression:
            for label, val in self.satisfied.items():
                res.append(['    LABEL: %s = %s' %
                            (label, self.messages[label]), val])
            res.append(['CONDITION: %s' %
                        self.raw_conditional_expression, self.is_satisfied()])
        elif self.satisfied:
            for label, val in self.satisfied.items():
                res.append([self.messages[label], val])
        # (Else trigger wiped out by pre-initial simplification.)
        return res

    def set_satisfied(self):
        for label in self.messages:
            self.satisfied[label] = True
        if self.conditional_expression is None:
            self.all_satisfied = True
        else:
            self.all_satisfied = self._conditional_is_satisfied()

    def set_not_satisfied(self):
        for label in self.messages:
            self.satisfied[label] = False
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

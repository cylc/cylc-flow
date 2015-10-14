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

import re, sys
from cylc.conditional_simplifier import ConditionalSimplifier
from cylc.cycling.loader import get_point


"""A task prerequisite.

The concrete result of an abstract logical trigger expression.

"""


class TriggerExpressionError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)


class Prerequisite(object):

    # Extracts T from "foo.T succeeded" etc.
    CYCLE_POINT_RE = re.compile('^\w+\.(\S+) .*$')

    def __init__( self, owner_id, start_point=None ):
        self.owner_id = owner_id
        self.labels = {}   # labels[ message ] = label
        self.messages = {}   # messages[ label ] = message
        self.satisfied = {}    # satisfied[ label ] = True/False
        self.satisfied_by = {}   # self.satisfied_by[ label ] = task_id
        self.target_point_strings = []   # list of target cycle points
        self.start_point = start_point
        self.pre_initial_messages = []
        self.conditional_expression = None
        self.raw_conditional_expression = None

    def add(self, message, label, pre_initial=False):
        # Add a new prerequisite message in an UNSATISFIED state.
        self.messages[ label ] = message
        self.labels[ message ] = label
        self.satisfied[label]  = False
        m = re.match( self.__class__.CYCLE_POINT_RE, message )
        if m:
            self.target_point_strings.append( m.groups()[0] )
        if pre_initial:
            self.pre_initial_messages.append(label)

    def get_not_satisfied_list( self ):
        not_satisfied = []
        for label in self.satisfied:
            if not self.satisfied[ label ]:
                not_satisfied.append( label )
        return not_satisfied

    def set_condition( self, expr ):
        # 'foo | bar & baz'
        # 'foo:fail | foo'
        # 'foo[T-6]:out1 | baz'

        drop_these = []

        if self.pre_initial_messages:
            for k in self.pre_initial_messages:
                drop_these.append(k)

        # Needed to drop pre warm-start dependence:
        for k in self.messages:
            if k in drop_these:
                continue
            if self.start_point:
                task = re.search( r'(.*).(.*) ', self.messages[k])
                if task.group:
                    try:
                        foo = task.group().split(".")[1].rstrip()
                        if get_point( foo ) <  self.start_point:
                            drop_these.append(k)
                    except IndexError:
                        pass

        for label in drop_these:
            if self.messages.get(label):
                msg = self.messages[label]
                self.messages.pop(label)
                self.satisfied.pop(label)
                self.labels.pop(msg)

        if '|' in expr:
            if drop_these:
                simpler = ConditionalSimplifier(expr, drop_these)
                expr = simpler.get_cleaned()
            # Make a Python expression so we can eval() the logic.
            self.raw_conditional_expression = expr
            for label in self.messages:
                expr = re.sub( r'\b' + label + r'\b', 'self.satisfied[\'' + label + '\']', expr )
            self.conditional_expression = expr

    def is_satisfied( self ):
        if not self.satisfied:
            # No prerequisites left after pre-initial simplification.
            return True
        elif not self.conditional_expression:
            # Single trigger or several with '&' only; don't need eval.
            return all(self.satisfied.values())
        else:
            # Trigger expression with at least one '|': use eval.
            try:
                res = eval(self.conditional_expression)
            except Exception, x:
                print >> sys.stderr, 'ERROR:', x
                if str(x).find("unexpected EOF") != -1:
                    print >> sys.stderr, "(?could be unmatched parentheses in the graph string?)"
                raise TriggerExpressionError, '"' + self.raw_conditional_expression + '"'
            return res

    def satisfy_me( self, outputs ):
        # Can any completed outputs satisfy any of my prequisites?
        for label in self.satisfied:
            for msg in outputs:
                if self.messages[label] == msg:
                    self.satisfied[ label ] = True
                    self.satisfied_by[ label ] = outputs[msg] # owner_id

    def dump( self ):
        # TODO - CHECK THIS WORKS NOW
        # return an array of strings representing each message and its state
        res = []
        if self.raw_conditional_expression:
            for label, val in self.satisfied.items():
                res.append(['    LABEL: %s = %s' % (label, self.messages[label]), val])
            res.append(['CONDITION: %s' % self.raw_conditional_expression, self.is_satisfied()])
        elif self.satisfied:
            for label, val in self.satisfied.items():
                res.append([self.messages[label], val])
        # (Else trigger wiped out by pre-initial simplification.)
        return res

    def set_satisfied(self):
        for label in self.messages:
            self.satisfied[label] = True

    def set_not_satisfied(self):
        for label in self.messages:
            self.satisfied[label] = False

    def get_target_points( self ):
        """Return a list of cycle points target by each prerequisite,
        including each component of conditionals."""
        return [get_point(p) for p in self.target_point_strings]

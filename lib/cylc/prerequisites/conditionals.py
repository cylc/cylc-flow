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
from simplify import conditional_simplifier
from cylc.cycling.loader import get_point

# label1 => "foo ready for <CYCLE_POINT>
# label2 => "bar.<CYCLE_POINT> succeeded"
# expr   => "( [label1] or [label2] )"

class TriggerExpressionError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class conditional_prerequisites(object):

    # Extracts T from "foo.T succeeded" etc.
    CYCLE_POINT_RE = re.compile('^\w+\.(\S+) .*$')

    def __init__( self, owner_id, start_point=None ):
        self.owner_id = owner_id
        self.labels = {}   # labels[ message ] = label
        self.messages = {}   # messages[ label ] = message
        self.satisfied = {}    # satisfied[ label ] = True/False
        self.satisfied_by = {}   # self.satisfied_by[ label ] = task_id
        self.target_point_strings = []   # list of target cycle points
        self.auto_label = 0
        self.excess_labels = []
        self.start_point = start_point
        self.pre_initial_messages = []

    def add( self, message, label = None, pre_initial = False ):
        # Add a new prerequisite message in an UNSATISFIED state.
        if label:
            # TODO - autolabelling NOT USED? (and is broken because the
            # supplied condition is necessarily expressed in terms of
            # user labels?).
            pass
        else:
            self.auto_label += 1
            label = str( self.auto_label )

        if message in self.labels:
            # DUPLICATE PREREQUISITE - IMPOSSIBLE IN CURRENT USE OF THIS CLASS?
            # (TODO - if impossible, remove related code from this file)
            #raise SystemExit( "Duplicate prerequisite: " + message )
            print >> sys.stderr, "WARNING, " + self.owner_id + ": duplicate prerequisite: " + message
            self.excess_labels.append(label)
            return

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
        for k in self.messages:
            if self.start_point:
                task = re.search( r'(.*).(.*) ', self.messages[k])
                if task.group:
                    try:
                        foo = task.group().split(".")[1].rstrip()
                        if ( get_point( foo ) <  self.start_point and
                                 foo != '1' ):
                            # TODO - ASYNC TASKS '1' ONLY NEEDS UPDATING FOR
                            # INTEGER CYCLING (AND MORE?)
                            drop_these.append(k)
                    except IndexError:
                        pass

        if self.pre_initial_messages:
            for k in self.pre_initial_messages:
                drop_these.append(k)

        if drop_these:
            simpler = conditional_simplifier(expr, drop_these)
            expr = simpler.get_cleaned()

        # make into a python expression
        self.raw_conditional_expression = expr
        for label in self.messages:
            # match label start and end on on word boundary
            expr = re.sub( r'\b' + label + r'\b', 'self.satisfied[\'' + label + '\']', expr )

        for label in self.excess_labels:
            # treat duplicate triggers as always satisfied
            expr = re.sub( r'\b' + label + r'\b', 'True', expr )
            self.raw_conditional_expression = re.sub( r'\b' + label + r'\b', 'True', self.raw_conditional_expression )

        for label in drop_these:
            if self.messages.get(label):
                msg = self.messages[label]
                self.messages.pop(label)
                self.satisfied.pop(label)
                self.labels.pop(msg)

        self.conditional_expression = expr

    def all_satisfied( self ):
        if self.conditional_expression == "()":
            return True
        else:
            try:
                res = eval( self.conditional_expression )
            except Exception, x:
                print >> sys.stderr, 'ERROR:', x
                if str(x).find("unexpected EOF") != -1:
                    print >> sys.stderr, "(?could be unmatched parentheses in the graph string?)"
                raise TriggerExpressionError, '"' + self.raw_conditional_expression + '"'
            return res

    def count( self ):
        # how many messages are stored
        return len( self.satisfied.keys() )

    def dump( self ):
        # return an array of strings representing each message and its state
        res = []
        for label in self.satisfied:
            msg = self.messages[label]
            res.append( [ '    LABEL: ' + label + ' = ' + self.messages[label], self.satisfied[ label ] ]  )
        res.append( [     'CONDITION: ' + self.raw_conditional_expression, self.all_satisfied() ] )
        return res

    def set_all_satisfied( self ):
        for label in self.messages:
            self.satisfied[ label ] = True

    def set_all_unsatisfied( self ):
        for label in self.messages:
            self.satisfied[ label ] = False

    def get_target_points( self ):
        """Return a list of cycle points target by each prerequisite,
        including each component of conditionals."""
        return [get_point(p) for p in self.target_point_strings]

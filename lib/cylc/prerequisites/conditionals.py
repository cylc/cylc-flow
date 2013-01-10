#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re, sys

# label1 => "foo ready for <TAG>
# label2 => "bar%<TAG> succeeded"
# expr   => "( [label1] or [label2] )"

class TriggerExpressionError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class conditional_prerequisites(object):
    def __init__( self, owner_id ):
        self.owner_id = owner_id
        self.labels = {}   # labels[ message ] = label
        self.messages = {}   # messages[ label ] = message 
        self.satisfied = {}    # satisfied[ label ] = True/False
        self.satisfied_by = {}   # self.satisfied_by[ label ] = task_id
        self.auto_label = 0
        self.excess_labels = []

    def add( self, message, label = None ):
        # Add a new prerequisite message in an UNSATISFIED state.
        if label:
            # TO DO: autolabelling NOT USED? (and is broken because the
            # supplied condition is necessarily expressed in terms of
            # user labels?).
            pass
        else:
            self.auto_label += 1
            label = str( self.auto_label )

        if message in self.labels:
            # DUPLICATE PREREQUISITE - IMPOSSIBLE IN CURRENT USE OF THIS CLASS?
            # (TO DO: if impossible, remove related code from this file)
            #raise SystemExit( "Duplicate prerequisite: " + message )
            print >> sys.stderr, "WARNING, " + self.owner_id + ": duplicate prerequisite: " + message
            self.excess_labels.append(label)
            return

        self.messages[ label ] = message
        self.labels[ message ] = label
        self.satisfied[label]  = False

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

        # make into a python expression
        self.raw_conditional_expression = expr
        for label in self.messages:
            # match label start and end on on word boundary
            expr = re.sub( r'\b' + label + r'\b', 'self.satisfied[\'' + label + '\']', expr )
        for label in self.excess_labels:
            # treat duplicate triggers as always satisfied
            expr = re.sub( r'\b' + label + r'\b', 'True', expr )
            self.raw_conditional_expression = re.sub( r'\b' + label + r'\b', 'True', self.raw_conditional_expression )

        self.conditional_expression = expr

    def all_satisfied( self ):
        try:
            res = eval( self.conditional_expression )
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

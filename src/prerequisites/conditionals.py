#!/usr/bin/env python

# conditional prerequisites

import re, sys

# label1 => "foo ready for $CYCLE_TIME"
# label2 => "bar%$CYCLE_TIME succeeded"
# expr   => "( [label1] or [label2] )"

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
        # 'foo(T-6):out1 | baz'

        # make into a python expression
        self.raw_conditional_expression = expr
        for label in self.messages:
            # match label start and end on on word boundary
            expr = re.sub( r'\b' + label + r'\b', 'self.satisfied[\'' + label + '\']', expr )
        for label in self.excess_labels:
            expr = re.sub( r'\b' + label + r'\b', 'True', expr )
            self.raw_conditional_expression = re.sub( r'\b' + label + r'\b', 'True', self.raw_conditional_expression )

        self.conditional_expression = expr

    def all_satisfied( self ):
        res = eval( self.conditional_expression )
        return res
            
    def satisfy_me( self, outputs ):
        # can any completed outputs satisfy any of my prequisites?
        for label in self.get_not_satisfied_list():
            # for each of my unsatisfied prerequisites
            for output in outputs.get_satisfied_list():
                # compare it with each of the completed outputs
                if re.match( self.messages[label], output ):
                    self.satisfied[ label ] = True
                    self.satisfied_by[ label ] = outputs.owner_id

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

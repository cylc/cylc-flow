#!/usr/bin/env python

# conditional prerequisites

import re
from prerequisites import prerequisites

# label1 => "foo ready for $CYCLE_TIME"
# label2 => "bar%$CYCLE_TIME finished"
# expr   => "( [label1] or [label2] )"

class conditional_prerequisites(prerequisites):
    def __init__( self, owner_id ):
        self.labels = {}   # labels[ message ] = label
        self.messages = {}   # messages[ label ] = message 
        self.satisfied = {}    # satisfied[ label ] = True/False
        self.satisfied_by = {}   # self.satisfied_by[ label ] = task_id
        self.auto_label = 0

    def add( self, message, label = None ):
        # Add a new prerequisite message in an UNSATISFIED state.
        if label:
            pass
        else:
            self.auto_label += 1
            label = str( self.auto_label )

        if message in self.labels:
            raise SystemExit( "Duplicate prerequisite: " + message )
        print '> ', label, message
        self.messages[ label ] = message
        self.labels[ message ] = label
        self.satisfied[label] = False

    def get_not_satisfied_list( self ):
        not_satisfied = []
        for label in self.satisfied:
            if not self.satisfied[ label ]:
                not_satisfied.append( label )
        return not_satisfied

    def set_condition( self, expr ):
        # 'foo | bar & baz'
        # make into a python expression
        for l in self.messages:
            # must use raw string here else '\b' means 'backspace'
            # instead of 'word boundary'
            expr = re.sub( r'\b'+l+r'\b', "self.satisfied['" + l + "']", expr )
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
        for key in self.satisfied:
            res.append( [ self.messages[key], self.satisfied[ key ] ]  )
        return res

    def set_all_satisfied( self ):
        for label in self.messages:
            self.satisfied[ label ] = True

    def set_all_unsatisfied( self ):
        for label in self.messages:
            self.satisfied[ label ] = False

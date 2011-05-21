#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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

import re

# PREREQUISITES: A collection of messages representing the prerequisite
# conditions for a task, each of which can be "satisfied" or not.  An
# unsatisfied prerequisite becomes satisfied if it matches a satisfied
# output message from another task (via the cylc requisite broker).

class plain_prerequisites(object):
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
        self.messages[ label ] = message
        self.labels[ message ] = label
        self.satisfied[label] = False

    def get_not_satisfied_list( self ):
        not_satisfied = []
        for label in self.satisfied:
            if not self.satisfied[ label ]:
                not_satisfied.append( label )
        return not_satisfied

    def all_satisfied( self ):
        return not ( False in self.satisfied.values() ) 
            
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

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

import re, sys

# OUTPUTS:
# A collection of messages representing the outputs of ONE TASK.

class outputs( object ):
    def __init__( self, owner_id ):

        self.owner_id = owner_id
        # Store completed and not-completed outputs in separate 
        # dicts to allow quick passing of completed to the broker.

        # Using rhs of dict as a cheap way to get owner ID to receiving
        # tasks via the dependency broker object:
        # self.(not)completed[message] = owner_id

        self.completed = {}
        self.not_completed = {}

    def count( self ):
        return len( self.completed ) + len( self.not_completed )

    def count_satisfied( self ):
        return len( self.completed )

    def dump( self ):
        # return a list of strings representing each message and its state
        res = []
        for key in self.not_completed:
            res.append( [ key, False ]  )
        for key in self.completed:
            res.append( [ key, True ]  )
        return res

    def all_satisfied( self ):
        if len( self.not_completed ) == 0:
            return True
        else:
            return False

    def is_satisfied( self, message ):
        if message in self.completed:
            return True
        else:
            return False

    def set_satisfied( self, message ):
        try:
            del self.not_completed[message]
        except:
            pass
        self.completed[ message ] = self.owner_id

    def exists( self, message ):
        if message in self.completed or message in self.not_completed:
            return True
        else:
            return False

    def set_all_unsatisfied( self ):
        for message in self.completed.keys():
            del self.completed[message]
            self.not_completed[ message ] = self.owner_id

    def set_all_satisfied( self ):
        for message in self.not_completed.keys():
            del self.not_completed[message]
            self.completed[ message ] = self.owner_id

    def get_satisfied( self ):
        return self.completed

    def get_satisfied_list( self ):
        return self.completed.keys()

    def get_not_satisfied_list( self ):
        return self.not_completed.keys()

    def get_list( self ):
        return self.completed.keys() + self.not_completed.keys()

    def add( self, message ):
        # Add a new not-completed output message
        if message in self.completed:
            # duplicate output messages are an error.
            print >> sys.stderr, 'ERROR: already registered: ' + message
            sys.exit(1)
        self.not_completed[message] = self.owner_id

    def remove( self, message ):
        try:
            del self.completed[ message ]
            del self.not_completed[ message ]
        except:
            print >> sys.stderr, 'WARNING: not such output to delete:'
            print >> sys.stderr, message


    def register( self ):
        # automatically define special 'started' and 'succeeded' outputs
        # TO DO: just use two calls to add()?
        message = self.owner_id + ' started'
        self.not_completed[ message ] = self.owner_id
        self.add( self.owner_id + ' succeeded' )

    def set_all_incomplete( self ):
        self.set_all_unsatisfied()

    def set_all_complete( self ):
        self.set_all_satisfied()

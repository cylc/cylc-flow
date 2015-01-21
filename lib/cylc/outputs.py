#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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

    def count_completed( self ):
        return len( self.completed )

    def dump( self ):
        # return a list of strings representing each message and its state
        res = []
        for key in self.not_completed:
            res.append( [ key, False ]  )
        for key in self.completed:
            res.append( [ key, True ]  )
        return res

    def all_completed( self ):
        if len( self.not_completed ) == 0:
            return True
        else:
            return False

    def is_completed( self, message ):
        if message in self.completed:
            return True
        else:
            return False

    def set_completed( self, message ):
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

    def set_all_incomplete( self ):
        for message in self.completed.keys():
            del self.completed[message]
            self.not_completed[ message ] = self.owner_id

    def set_all_completed( self ):
        for message in self.not_completed.keys():
            del self.not_completed[message]
            self.completed[ message ] = self.owner_id

    def add( self, message, completed=False ):
        # Add a new output message
        if message in self.completed or message in self.not_completed:
            # duplicate output messages are an error.
            print >> sys.stderr, 'WARNING: output already registered: ' + message
        if not completed:
            self.not_completed[message] = self.owner_id
        else:
            self.completed[message] = self.owner_id

    def remove( self, message, fail_silently=False ):
        if message in self.completed:
            del self.completed[ message ]
        elif message in self.not_completed:
            del self.not_completed[ message ]
        elif not fail_silently:
            print >> sys.stderr, 'WARNING: no such output to delete:'
            print >> sys.stderr, ' => ', message

    def register( self ):
        # automatically define special outputs common to all tasks
        self.add( self.owner_id + ' submitted' )
        self.add( self.owner_id + ' started' )
        self.add( self.owner_id + ' succeeded' )

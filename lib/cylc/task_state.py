#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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
import sys

"""
Store task state information, and provide methods to dump and reload
this information from the cylc state dump file. Use of a dict data
structure allows derived task classes to set arbitrary new state
variables that will automatically be written to and read from the state
dump file.
"""

# TO DO: need some exception handling in here

class task_state(object):

    allowed_status = [ 'waiting', 'retry_delayed', 'submitted',
            'running', 'succeeded', 'failed', 'held', 'runahead',
            'queued' ]

    # INTERNALLY TO THIS CLASS, SPAWNED STATUS IS A STRING
    allowed_bool = [ 'true', 'false' ]

    def __init__( self, initial_state ):

        self.state = {}

        if not initial_state:
            # defaults
            self.state[ 'status' ] = 'waiting'
            self.state[ 'spawned' ] = 'false'
        else:
            # could be a state dump file entry
            # or a raw string ('waiting' etc.)
            self.state = self.parse( initial_state )
            self.check()

    def has_key( self, key ):
        if key in self.state.keys():
            return True
        else:
            return False

    def set_status( self, value ):
        if value in task_state.allowed_status:
            self.state[ 'status' ] = value
            return True
        else:
            return False

    def get_status( self ):
        return self.state[ 'status' ]

    def set_spawned( self ):
        self.state[ 'spawned' ] = 'true'

    def has_spawned( self ):
        if self.state[ 'spawned' ] == 'true':
            return True
        else:
            return False

    def is_succeeded( self ):
        if self.state[ 'status' ] == 'succeeded':
            return True
        else:
            return False

    def is_failed( self ):
        if self.state[ 'status' ] == 'failed':
            return True
        else:
            return False

    def is_waiting( self ):
        if self.state[ 'status' ] == 'waiting' or \
        self.state[ 'status' ] == 'retry_delayed':
            return True
        else:
            return False

    def is_submitted( self ):
        if self.state[ 'status' ] == 'submitted':
            return True
        else:
            return False

    def is_running( self ):
        if self.state[ 'status' ] == 'running':
            return True
        else:
            return False

    def is_held( self ):
        if self.state[ 'status' ] == 'held':
            return True
        else:
            return False

    def is_runahead( self ):
        if self.state[ 'status' ] == 'runahead':
            return True
        else:
            return False

    def is_queued( self ):
        if self.state[ 'status' ] == 'queued':
            return True
        else:
            return False

    def is_retry_delayed( self ):
        if self.state[ 'status' ] == 'retry_delayed':
            return True
        else:
            return False

    # generic set for special dumpable state required by some tasks.
    def set( self, item, value ):
        self.state[ item ] = value

    # generic get for special dumpable state required by some tasks.
    def get( self, item ):
        return self.state[ item ]

    def check( self ):
        # check compulsory items have been defined correctly
        if 'status' not in self.state:
            print 'ERROR, run status not defined'
            sys.exit(1)

        if self.state[ 'status' ] not in task_state.allowed_status:
            print 'ERROR, illegal run status:', self.state[ 'status' ]
            sys.exit(1)

        if 'spawned' not in self.state:
            print 'ERROR, abdication status not defined'
            sys.exit(1)

        if self.state[ 'spawned' ] not in task_state.allowed_bool:
            print 'ERROR, illegal abdication status:', self.state[ 'spawned' ]
            sys.exit(1)

    def dump( self ):
        # format: 'item1=value1, item2=value2, ...'
        result = ''
        for key in self.state:
            result += key + '=' + str( self.state[ key ] ) + ', '
        result = result.rstrip( ', ' )
        return result

    def parse( self, input ):
        state = {}

        if input in task_state.allowed_status:
            state[ 'status' ] = input
            # ASSUME THAT ONLY succeeded TASKS, AT STARTUP, HAVE spawned 
            # (in fact this will only be used to start tasks in 'waiting')
            if input == 'succeeded':
                state[ 'spawned' ] = 'true'
            else:
                state[ 'spawned' ] = 'false'

        else:
            # reconstruct state from a dumped state string
            pairs = input.split( ', ' )
            for pair in pairs:
                [ item, value ] = pair.split( '=' )
                state[ item ] = value

        return state

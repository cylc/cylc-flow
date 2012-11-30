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

class TaskStateError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class task_state(object):

    legal = [ 'waiting',
              'retry_delayed',
              'submitted',
              'running',
              'succeeded',
              'failed',
              'held',
              'runahead',
              'queued' ]

    @classmethod
    def is_legal( cls, state ):
        return state in cls.legal

    # Note: internal to this class, task spawned status is string 'true' or 'false'

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

    def set_status( self, state ):
        if self.__class__.is_legal( state ):
            self.state[ 'status' ] = state
        else:
            raise TaskStateError, 'Illegal task state: ' + state

    def get_status( self ):
        return self.state[ 'status' ]

    def set_spawned( self ):
        self.state[ 'spawned' ] = 'true'

    def has_spawned( self ):
        return self.state[ 'spawned' ] == 'true'

    def is_currently( self, state ):
        return state == self.state[ 'status' ]

    # generic set for special dumpable state required by some tasks.
    def set( self, item, value ):
        self.state[ item ] = value

    # generic get for special dumpable state required by some tasks.
    def get( self, item ):
        return self.state[ item ]

    def check( self ):
        # check compulsory items have been defined correctly
        if 'status' not in self.state:
            raise TaskStateError, 'ERROR, run status not defined'
        if not self.__class__.is_legal( self.state[ 'status' ] ):
            raise TaskStateError, 'ERROR, illegal run status: ' + str( self.state[ 'status' ])
        if 'spawned' not in self.state:
            raise TaskStateError, 'ERROR, task spawned status not defined'
        if self.state[ 'spawned' ] not in [ 'true', 'false' ]:
            raise TaskStateError, 'ERROR, illegal task spawned status: ' + str( self.state[ 'spawned' ])
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

        if input in self.__class__.legal:
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

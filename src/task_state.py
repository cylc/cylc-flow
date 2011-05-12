#!/usr/bin/env python


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

    allowed_status = [ 'waiting', 'submitted', 'running', 'finished', 'failed', 'stopped', 'neutral' ]
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

    def is_finished( self ):
        if self.state[ 'status' ] == 'finished':
            return True
        else:
            return False

    def is_failed( self ):
        if self.state[ 'status' ] == 'failed':
            return True
        else:
            return False

    def is_waiting( self ):
        if self.state[ 'status' ] == 'waiting':
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

    def is_stopped( self ):
        if self.state[ 'status' ] == 'stopped':
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

        #if 'cycle_time' not in self.state:
        #    print 'ERROR, cycle time not defined'
        #    sys.exit(1)

        #if not cycle_time.is_valid( self.state[ 'cycle_time' ] ):
        #    print 'ERROR, invalid cycle time', self.state[ 'cycle_time' ]
        #    sys.exit(1)

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
            # ASSUME THAT ONLY FINISHED TASKS, AT STARTUP, HAVE spawned 
            # (in fact this will only be used to start tasks in 'waiting')
            if input == 'finished':
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

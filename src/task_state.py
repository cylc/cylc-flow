#!/usr/bin/python

#import reference_time
import sys

"""
Store, and provide methods to interact with, the internal task state
information that needs to be dumped and reloaded from state dump file.
"""

class task_state:

    allowed_status = [ 'waiting', 'running', 'finished', 'failed' ]
    # INTERNALLY TO THIS CLASS, ABDICATION STATUS IS A STRING
    allowed_abdicated = [ 'true', 'false' ]

    def __init__( self, initial_state = None ):

        self.state = {}

        if not initial_state:
            # defaults
            self.state[ 'status' ] = 'waiting'
            self.state[ 'abdicated' ] = 'false'
            #self.state[ 'reference_time' ] = '9999010100'

        else:
            self.state = self.parse( initial_state )
            self.check()

            if self.is_running() or self.is_failed():
                # Running or failed tasks need to re-run at startup.
                self.set_status( 'waiting' )


    def set_status( self, value ):
        if value in task_state.allowed_status:
            self.state[ 'status' ] = value
            return True
        else:
            return False

    def get_status( self ):
        return self.state[ 'status' ]

    def set_abdicated( self ):
        self.state[ 'abdicated' ] = 'true'

    def has_abdicated( self ):
        if self.state[ 'abdicated' ] == 'true':
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

    def is_running( self ):
        if self.state[ 'status' ] == 'running':
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

        if 'abdicated' not in self.state:
            print 'ERROR, abdication status not defined'
            sys.exit(1)

        if self.state[ 'abdicated' ] not in task_state.allowed_abdicated:
            print 'ERROR, illegal abdication status:', self.state[ 'abdicated' ]
            sys.exit(1)

        #if 'reference_time' not in self.state:
        #    print 'ERROR, reference time not defined'
        #    sys.exit(1)

        #if not reference_time.is_valid( self.state[ 'reference_time' ] ):
        #    print 'ERROR, invalid reference time', self.state[ 'reference_time' ]
        #    sys.exit(1)

    def dump( self ):
        # format: 'item1=value1, item2=value2, ...'
        result = ''
        for key in self.state:
            result += key + '=' + str( self.state[ key ] ) + ', '
        result = result.rstrip( ', ' )
        return result

    def parse( self, dump ):
        # reconstruct state from a dumped state string
        state = {}
        pairs = dump.split( ', ' )
        for pair in pairs:
            [ item, value ] = pair.split( '=' )
            state[ item ] = value

        return state

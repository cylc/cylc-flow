#!/usr/bin/env python


from cycling import cycling
from oneoff import oneoff
import re

class cycling_daemon( oneoff, cycling ):
    # A oneoff task that adds outputs dynamically as messages matching
    # registered patterns come in. The corresponding real task may keep
    # running indefinitely, e.g. to watch for incoming external data.

    # not 'daemon' - hasattr(task, 'daemon') returns True for all tasks 
    # due to the pyro daemon (I think).
    daemon_task = True  

    def __init__( self, state ):

        m = re.match( '(\d{10}) \| (.*)', state )
        if m:
            # loading from state dump
            ( self.last_reported, state ) = m.groups()
        else:
            self.last_reported = self.c_time

        self.env_vars[ 'START_CYCLE_TIME' ] = self.last_reported

        cycling.__init__( self, state )


    def incoming( self, priority, message ):
        # intercept incoming messages and check for a pattern match 
        for pattern in self.output_patterns:
            m = re.match( pattern, message )
            if m:
                self.outputs.add( 10, message )
                ctime = m.groups()[0]
                self.last_reported = ctime

        cycling.incoming( self, priority, message )

    def dump_state( self, FILE ):
        # Write state information to the state dump file
        # This must be compatible with __init__() on reload
        FILE.write( self.id + ' : ' + self.last_reported + ' | ' + self.state.dump() + '\n' )

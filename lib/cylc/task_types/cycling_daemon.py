#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

""" NOTE: THIS CLASS HAS NOT BEEN USED SINCE CYLC-2; IT MAY NEED UPDATING."""

from cycling import cycling
from oneoff import oneoff
import re

class cycling_daemon( oneoff, cycling ):
    # A one off task that adds outputs dynamically as messages matching
    # registered patterns come in. The corresponding real task may keep
    # running indefinitely, e.g. to watch for incoming external data.

    is_daemon = True

    def __init__( self, state, validate=False ):

        m = re.match( '(\d{10}) \| (.*)', state )
        if m:
            # loading from state dump
            ( self.last_reported, state ) = m.groups()
        else:
            self.last_reported = self.c_time

        self.env_vars[ 'START_CYCLE_TIME' ] = self.last_reported

        cycling.__init__( self, state, validate )


    def process_incoming_message( self, (priority,message) ):
        # intercept incoming messages and check for a pattern match 
        for pattern in self.output_patterns:
            m = re.match( pattern, message )
            if m:
                self.outputs.add( 10, message )
                ctime = m.groups()[0]
                self.last_reported = ctime

        cycling.process_incoming_message( self, (priority,message) )

    def dump_state( self, FILE ):
        # Write state information to the state dump file
        # This must be compatible with __init__() on reload
        FILE.write( self.id + ' : ' + self.last_reported + ' | ' + self.state.dump() + '\n' )

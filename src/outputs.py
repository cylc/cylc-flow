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
import sys
from requisites import requisites

# OUTPUTS:
# A collection of messages with associated times, representing the
# outputs of ONE TASK and their estimated completion times. 
# "Satisfied" => the output has been completed.

class outputs( requisites ):
    # outputs are requisites for which each message represents an
    # output or milestone that has either been completed (satisfied) or
    # not (not satisfied).

    # additionally, each output message has an associated estimated
    # completion time, used to simulate task execution in simulation mode.

    def __init__( self, owner_id ):
        self.ordered = [] 
        requisites.__init__( self, owner_id )
        # automatically define special 'started' and 'succeeded' outputs

    def add( self, message ):
        # Add a new unsatisfied output message for time t
        if message in self.satisfied.keys():
            # duplicate output messages are an error.
            print 'ERROR: already registered: ' + message
            sys.exit(1)
        self.satisfied[message] = False
        self.ordered.append( message )

    def remove( self, message ):
        # calling function should catch exceptions due to attempting to
        # delete a non-existent item.
        del self.satisfied[ message ]
        self.ordered.remove( message )

    def register( self ):
        message = self.owner_id + ' started'
        self.satisfied[ message ] = False
        self.ordered.insert(0, message )
        self.add( self.owner_id + ' succeeded' )

    def get_ordered( self ):
        return self.ordered

    def set_all_incomplete( self ):
        requisites.set_all_unsatisfied( self )

    def set_all_complete( self ):
        requisites.set_all_satisfied( self )

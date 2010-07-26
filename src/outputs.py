#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

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
    # completion time, used to simulate task execution in dummy mode.

    def __init__( self, owner_id ):
        self.ordered = [] 
        requisites.__init__( self, owner_id )
        # automatically define special 'started' and 'finished' outputs

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

        # and 'completed' for dependant tasks that don't care about
        # success or failure of this task, only completion
        self.add( self.owner_id + ' completed' )
        self.add( self.owner_id + ' finished' )

    def get_ordered( self ):
        return self.ordered

    def set_all_incomplete( self ):
        requisites.set_all_unsatisfied( self )

    def set_all_complete( self ):
        requisites.set_all_satisfied( self )

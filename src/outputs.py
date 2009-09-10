#!/usr/bin/python

import re
import sys
import logging
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

    def __init__( self, task_name, ref_time ):
        self.task_name = task_name
        self.ref_time = ref_time

        self.message = {}    # self.message[ t ] = "message"
        self.time = {}       # self.time[ "message" ] = t

        requisites.__init__( self )

    def add( self, t, message ):
        # Add a new unsatisfied output message for time t

        log = logging.getLogger( "main." + self.task_name )            

        if message in self.satisfied.keys():
            # duplicate output messages are an error.
            log.critical( 'already registered: ' + message ) 
            sys.exit(1)

        if t in self.message.keys():
            # The system cannot currently handle multiple outputs
            # generated at the same time; only the last will be
            # registered, the others get overwritten. 

            log.critical( 'two outputs registered for ' + str(t) + ' minutes' )
            log.critical( '(may mean the last output is at the task finish time)' ) 
            log.critical( ' one: "' + self.message[ t ] + '"' )
            log.critical( ' two: "' + message + '"' )
            sys.exit(1)

        self.satisfied[message] = False
        self.message[ t ] = message
        self.time[message] = t

    def get_timed_requisites( self ):
        return self.message

    def set_all_incomplete( self ):
        requisites.set_all_unsatisfied( self )

    def set_all_completed( self ):
        requisites.set_all_satisfied( self )

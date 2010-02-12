#!/usr/bin/python

import logging
from requisites import requisites

# PREREQUISITES:
# A collection of messages representing the prerequisite conditions
# of ONE TASK. "Satisfied" => the prerequisite has been satisfied.
# Prerequisites can interact with a broker (above) to get satisfied.

class prerequisites( requisites ):

    # prerequisites are requisites for which each message represents a
    # prerequisite condition that is either satisifed or not satisfied.

    # prerequisite messages can change state from unsatisfied to
    # satisfied if another object has a matching output message that is
    # satisfied (i.e. a completed output). 

    def __init__( self, task_name, c_time ):
        self.task_name = task_name
        self.c_time = c_time

        requisites.__init__( self )

    def add( self, message ):
        # Add a new prerequisite message in an UNSATISFIED state.
        # We don't need to check if the new prerequisite message has
        # already been registered because duplicate prerequisites add no
        # information.
        self.satisfied[message] = False

    def satisfy_me( self, outputs, owner_id ):
        log = logging.getLogger( "main." + self.task_name )            
        # can any completed outputs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for output in outputs.satisfied.keys():
                    # compare it with each of the outputs
                    if output == prereq and outputs.satisfied[output]:
                        # if they match, my prereq has been satisfied
                        self.set_satisfied( prereq )
                        # TO LOG WHAT GOT SATISFIED BY WHOM:
                        log.debug( '[' + self.c_time + '] Got "' + output + '" from ' + owner_id )

    def will_satisfy_me( self, outputs, owner_id ):
        # return True if the outputs, when completed, would satisfy any of my prequisites
        for prereq in self.satisfied.keys():
            #print "PRE: " + prereq
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for output in outputs.satisfied.keys():
                    #print "POST: " + output
                    # compare it with each of the outputs
                    if output == prereq:   # (DIFFERENT FROM ABOVE HERE)
                        # if they match, my prereq has been satisfied
                        # self.set_satisfied( prereq )
                        return True

        return False

#!/usr/bin/python

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
import logging
from prerequisites import prerequisites

# PREREQUISITES:
# A collection of messages representing the prerequisite conditions
# of ONE TASK. "Satisfied" => the prerequisite has been satisfied.
# Prerequisites can interact with a broker (above) to get satisfied.

class loose_prerequisites( prerequisites ):

    def add( self, message ):
        # TO DO: CHECK FOR LOOSE PATTERN HERE
        # see fuzzy_prerequisites for example
        prerequisites.add( self, message )

    def sharpen_up( self, loose, sharp ):
        # replace a loose prerequisite with the actual output message
        # that satisfied it, and set it satisfied. This allows the task
        # run() method to know the actual output message.
        del self.satisfied[ loose ]
        self.satisfied[ sharp ] = True

    def satisfy_me( self, outputs, exclusions ):
        log = logging.getLogger( "main." + self.task_name )            
        # can any completed outputs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if it is not yet satisfied
                matched = False
                for output in outputs.satisfied.keys():
                    if output in exclusions:
                        continue
                    if outputs.satisfied[output]:
                        if re.match( prereq, output ):
                            matched = True
                            # breaks out ONE LEVEL right?
                            break

                if matched:
                    # replace fuzzy prereq with the actual output that satisfied it
                    self.sharpen_up( prereq, output )
                    log.debug( '[' + self.c_time + '] Got "' + output + '" from ' + outputs.owner_id )
                    self.satisfied_by[ prereq ] = outputs.owner_id

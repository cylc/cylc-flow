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
from prerequisites import prerequisites

# PREREQUISITES:
# A collection of messages representing the prerequisite conditions
# of ONE TASK. "Satisfied" => the prerequisite has been satisfied.
# Prerequisites can interact with a broker (above) to get satisfied.

class loose_prerequisites( prerequisites ):

    def __init__( self, owner_id ):
        self.match_group = {}
        prerequisites.__init__( self, owner_id )

    def add( self, message ):
        # TO DO: CHECK FOR LOOSE PATTERN HERE
        # see fuzzy_prerequisites for example
        prerequisites.add( self, message )

    def sharpen_up( self, loose, sharp ):
        # replace a loose prerequisite with the actual output message
        # that satisfied it, and set it satisfied.
        del self.satisfied[ loose ]
        self.satisfied[ sharp ] = True

    def satisfy_me( self, outputs, exclusions ):
        # can any completed outputs satisfy any of my prequisites?
        for prereq in self.get_not_satisfied_list():
            # for each of my unsatisfied prerequisites
            matched = False
            for output in outputs.get_satisfied_list():
                # for each completed output
                if output in exclusions:
                    continue
                if prereq == output:
                    continue
                m = re.match( prereq, output )
                if m:
                    match_group = m.groups()[0]
                    # replace fuzzy prereq with the actual output that satisfied it
                    self.match_group[ output ] = match_group 
                    self.satisfied_by[ output ] = outputs.owner_id
                    self.sharpen_up( prereq, output )
                    break

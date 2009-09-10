#!/usr/bin/python

import re
import sys
import logging
from prerequisites import prerequisites

# PREREQUISITES:
# A collection of messages representing the prerequisite conditions
# of ONE TASK. "Satisfied" => the prerequisite has been satisfied.
# Prerequisites can interact with a broker (above) to get satisfied.

# FUZZY_PREREQUISITES:
# For reference-time based prerequisites of the form "X more recent than
# or equal to this reference time". A delimited time cutoff is expected
# in the message string. Requires a more complex satisfy_me() method.

class fuzzy_prerequisites( prerequisites ):
    def add( self, message ):

        # check for fuzziness before pass on to the base class method

        # extract fuzzy reference time bounds from my prerequisite
        m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( message )
        if not m:
            log = logging.getLogger( "main." + self.task_name )            
            log.critical( '[' + self.ref_time + '] No fuzzy bounds MIN:MAX detected:' )
            log.critical( '[' + self.ref_time + '] -> ' + message )
            sys.exit(1)

        prerequisites.add( self, message )

    def sharpen_up( self, fuzzy, sharp ):
        # replace a fuzzy prerequisite with the actual output message
        # that satisfied it, and set it satisfied. This allows the task
        # run() method to know the actual output message.
        del self.satisfied[ fuzzy ]
        self.satisfied[ sharp ] = True

    def satisfy_me( self, outputs, owner_id ):
        log = logging.getLogger( "main." + self.task_name )            
        # can any completed outputs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if it is not yet satisfied

                # extract fuzzy reference time bounds from my prerequisite
                m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( prereq )
                #if not m:
                #NOT NEEDED: CHECKING IN ADD() NOW, ABOVE
                #    log.critical( '[' + self.ref_time + '] FAILED TO MATCH MIN:MAX IN ' + prereq )
                #    sys.exit(1)

                [ my_start, my_minmax, my_end ] = m.groups()
                [ my_min, my_max ] = my_minmax.split(':')

                possible_satisfiers = {}
                found_at_least_one = False
                for output in outputs.satisfied.keys():

                    if outputs.satisfied[output]:
                        # extract reference time from other's output
                        # message

                        m = re.compile( "^(.*)(\d{10})(.*)$").match( output )
                        if not m:
                            # this output can't possibly satisfy a
                            # fuzzy; move on to the next one.
                            continue
                
                        [ other_start, other_reftime, other_end ] = m.groups()

                        if other_start == my_start and other_end == my_end and other_reftime >= my_min and other_reftime <= my_max:
                            possible_satisfiers[ other_reftime ] = output
                            found_at_least_one = True
                        else:
                            continue

                if found_at_least_one: 
                    # choose the most recent possible satisfier
                    possible_reftimes = possible_satisfiers.keys()
                    possible_reftimes.sort( key = int, reverse = True )
                    chosen_reftime = possible_reftimes[0]
                    chosen_output = possible_satisfiers[ chosen_reftime ]

                    #print "FUZZY PREREQ: " + prereq
                    #print "SATISFIED BY: " + chosen_output

                    # replace fuzzy prereq with the actual output that satisfied it
                    self.sharpen_up( prereq, chosen_output )
                    log.debug( '[' + self.ref_time + '] Got "' + chosen_output + '" from ' + owner_id )

#    def will_satisfy_me( self, outputs, owner_id ):
# TO DO: THINK ABOUT HOW FUZZY PREREQS AFFECT THIS FUNCTION ...
#        # will another's outputs, if/when completed, satisfy any of my
#        # prequisites?
#
#        # this is similar to satisfy_me() but we don't need to know the most
#        # recent satisfying output message, just if any one can do it.
#
#        for prereq in self.satisfied.keys():
#            # for each of my prerequisites
#            if not self.satisfied[ prereq ]:
##                # if my prerequisite is not already satisfied
#
#                # extract reference time from my prerequisite
#                m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( prereq )
#                if not m:
#                    #log.critical( "FAILED TO MATCH MIN:MAX IN " + prereq )
#                    sys.exit(1)
#
#                [ my_start, my_minmax, my_end ] = m.groups()
#                [ my_min, my_max ] = my_minmax.split(':')
#
#                for output in outputs.satisfied.keys():
#
#                    # extract reference time from other's output message
#                    m = re.compile( "^(.*)(\d{10})(.*)$").match( output )
#                    if not m:
#                        # this output can't possibly satisfy a
#                        # fuzzy; move on to the next one.
#                        continue
#
#                    [ other_start, other_reftime, other_end ] = m.groups()
#
#                    if other_start == my_start and other_end == my_end and other_reftime >= my_min and other_reftime <= my_max:
#                        self.sharpen_up( prereq, output )

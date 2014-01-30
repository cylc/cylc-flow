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

import re
import sys
import logging
from prerequisites import prerequisites

# PREREQUISITES:
# A collection of messages representing the prerequisite conditions
# of ONE TASK. "Satisfied" => the prerequisite has been satisfied.
# Prerequisites can interact with a broker (above) to get satisfied.

# FUZZY_PREREQUISITES:
# For cycle-time based prerequisites of the form "X more recent than
# or equal to this cycle time". A delimited time cutoff is expected
# in the message string. Requires a more complex satisfy_me() method.

# TODO - THIS NEEDS TO BE UPDATED FOR NEW PREREQUISITE AND OUTPUT
# HANDLING.  SEE LOOSE_PREREQUISITES AS AN EXAMPLE.

class fuzzy_prerequisites( prerequisites ):

    def add( self, message ):

        # check for fuzziness before pass on to the base class method

        # extract fuzzy cycle time bounds from my prerequisite
        m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( message )
        if not m:
            # ADD ARTIFICIAL BOUNDS
            # TODO - this is a hack, find a better way.
            m = re.compile( "^(.*)(\d{10})(.*)$").match( message )
            if m:
                [ one, two, three ] = m.groups()
                bounds = two + ':' + two
                message = re.sub( '\d{10}', bounds, message )
            else:
                log = logging.getLogger( "main." + self.task_name )
                log.critical( '[' + self.c_time + '] No fuzzy bounds or ref time detected:' )
                log.critical( '[' + self.c_time + '] -> ' + message )
                sys.exit(1)

        prerequisites.add( self, message )

    def sharpen_up( self, fuzzy, sharp ):
        # replace a fuzzy prerequisite with the actual output message
        # that satisfied it, and set it satisfied. This allows the task
        # run() method to know the actual output message.
        del self.satisfied[ fuzzy ]
        self.satisfied[ sharp ] = True

    def satisfy_me( self, outputs ):
        log = logging.getLogger( "main." + self.task_name )
        # can any completed outputs satisfy any of my unsatisfied prequisites?
        for prereq in self.get_not_satisfied_list():
            # for each of my unsatisfied prerequisites
            # extract fuzzy cycle time bounds from my prerequisite
            m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( prereq )
            [ my_start, my_minmax, my_end ] = m.groups()
            [ my_min, my_max ] = my_minmax.split(':')

            possible_satisfiers = {}
            found_at_least_one = False
            for output in outputs.get_satisfied_list():
                m = re.compile( "^(.*)(\d{10})(.*)$").match( output )
                if not m:
                    # this output can't possibly satisfy a fuzzy so move on
                    continue

                    [ other_start, other_ctime, other_end ] = m.groups()

                    if other_start == my_start and other_end == my_end and other_ctime >= my_min and other_ctime <= my_max:
                        possible_satisfiers[ other_ctime ] = output
                        found_at_least_one = True
                    else:
                        continue

            if found_at_least_one:
                # choose the most recent possible satisfier
                possible_ctimes = possible_satisfiers.keys()
                possible_ctimes.sort( key = int, reverse = True )
                chosen_ctime = possible_ctimes[0]
                chosen_output = possible_satisfiers[ chosen_ctime ]

                #print "FUZZY PREREQ: " + prereq
                #print "SATISFIED BY: " + chosen_output

                # replace fuzzy prereq with the actual output that satisfied it
                self.sharpen_up( prereq, chosen_output )
                log.debug( '[' + self.c_time + '] Got "' + chosen_output + '" from ' + outputs.owner_id )
                self.satisfied_by[ prereq ] = outputs.owner_id

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
from prerequisites import prerequisites

# THIS IS USED WITH ASYNCHRONOUS TASKS (EXPERIMENTAL)

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
        #try:
        #    outputs.exclusions
        #except AttributeError:
        #    exclusions = []
        #else:
        #    exclusions = outputs.exclusions

        # can any completed outputs satisfy any of my prequisites?
        for prereq in self.get_not_satisfied_list():
            # for each of my unsatisfied prerequisites
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

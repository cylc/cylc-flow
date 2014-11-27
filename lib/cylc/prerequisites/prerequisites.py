#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
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

class prerequisites(object):
    """A container for other prerequisite types."""

    def __init__( self, start_point=None ):
        self.container = []
        self.start_point = start_point

    def add_requisites( self, reqs ):
        self.container.append( reqs )

    def get_satisfied_list( self ):
        satisfied = []
        for reqs in self.container:
            satisfied.append( reqs.get_satisfied() )
        return satisfied

    def eval_all( self ):
        # used to test validity of conditional prerequisite expression.
        # (all_satisfied() is not sufficient as it breaks out early).
        for reqs in self.container:
            reqs.all_satisfied()

    def all_satisfied( self ):
        result = True
        for reqs in self.container:
            if not reqs.all_satisfied():
                result = False
                break
        return result

    def satisfy_me( self, outputs ):
        # Can any completed outputs satisfy any of my prerequisites?
        for reqs in self.container:
        ##    for label in reqs.satisfied:
        ##        for msg in outputs:
        ##            if reqs.messages[label] == msg:
        ##                reqs.satisfied[ label ] = True
        ##                reqs.satisfied_by[ label ] = outputs[msg]  # (owner_id)
            reqs.satisfy_me( outputs )

    def get_satisfied_by( self ):
        satisfied_by = {}
        for reqs in self.container:
            for label in reqs.satisfied_by.keys():
                satisfied_by[ label ] = reqs.satisfied_by[label]
        return satisfied_by

    def count( self ):
        # how many messages are stored
        count = 0
        for reqs in self.container:
            count += len( reqs.satisfied.keys() )
        return count

    def dump( self ):
        # return an array of strings representing each message and its state
        res = []
        for reqs in self.container:
            res += reqs.dump()
        return res

    def set_all_satisfied( self ):
        for reqs in self.container:
            for label in reqs.messages:
                reqs.satisfied[ label ] = True

    def set_all_unsatisfied( self ):
        for reqs in self.container:
            for label in reqs.messages:
                reqs.satisfied[ label ] = False

    def get_target_points( self ):
        """Return a list of cycle points target by each prerequisite,
        including each component of conditionals."""
        points = []
        for reqs in self.container:
            points += reqs.get_target_points()
        return points

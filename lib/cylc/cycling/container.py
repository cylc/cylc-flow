#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

class cycon( object ):
    """A container to hold multiple cyclers"""

    def __init__( self, cycs=[] ):
        self.cyclers = []
        self.add( cycs )

    def add( self, cycs ):
        self.cyclers += cycs

    def initial_adjust_up( self, T ):
        adjusted = []
        for cyc in self.cyclers:
            adj = cyc.initial_adjust_up(T) 
            adjusted.append(adj)
        adjusted.sort()
        return adjusted[0]

    def next( self, T ):
        adjusted = []
        for cyc in self.cyclers:
            adjusted.append( cyc.next(T) )
        adjusted.sort()
        return adjusted[0]

    def offset( self, T, n ):
        return self.cyclers[0].__class__.offset(T, n)


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

class rotator(object):
    def __init__( self, colors=[ '#fcc', '#cfc', '#bbf', '#ffb' ] ):
        self.colors = colors
        self.current_color = 0
    def get_color( self ):
        index = self.current_color
        if index == len( self.colors ) - 1:
            index = 0
        else:
            index += 1
        self.current_color = index
        return self.colors[ index ]

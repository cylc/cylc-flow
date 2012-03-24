#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
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

class cycler( object ):
    @classmethod
    def offset( cls ):
        raise SystemExit( "ERROR: base offset override required" )
    def __init__( self ):
        pass
    def initial_adjust_up( self, cycletime ):
        raise SystemExit( "ERROR: base cycler class override required" )
    def next( self, cycletime ):
        raise SystemExit( "ERROR: base cycler class override required" )
    def valid( self, cycletime ):
        raise SystemExit( "ERROR: base cycler class override required" )

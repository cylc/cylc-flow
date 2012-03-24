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

from cylc.cycle_time import ct
import cylc.cycling.base

class Daily( cylc.cycling.base.cycler ):
    @classmethod
    def offset( cls, icin, n ):
        # decrement n days 
        foo = ct(icin)
        foo.decrement( days=n )
        return foo.get()
 
    def __init__( self, HHmmss='010101', stride=1, delay=0 ):
        # TO DO: check validity of HHmmss and delay
        self.HHmmss = HHmmss
        self.delay = delay
        # stride in integer number of days
        try:
            # is stride (a string) a valid int?
            self.stride = int(stride)
        except ValueError:
            raise SystemExit( "ERROR: stride " + stride + " is not a valid integer." )

    def next( self, icin ):
        # add stride days
        foo = ct(icin)
        foo.increment( days=self.stride )
        return foo.get()

    def initial_adjust_up( self, icin ):
        # next or equal valid: equal as any year is valid
        foo = ct( icin )
        foo.increment( days=self.delay )
        return foo

    def valid( self, ctime ):
        # Any valid cycle time is a valid day
        # TO DO: Or strictly valid (check HHmmss)?
        return True


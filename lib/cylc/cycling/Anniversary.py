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

# TO DO: update as for the Daily class

class Anniversary( cylc.cycling.base.cycler ):
    @classmethod
    def offset( cls, icin, n ):
        # decrement n years (same MMDDHHmmss as year length varies)
        YYYY = icin[0:4]
        # TO DO: HANDLE years < 1000
        prv = str(int(YYYY)-int(n)) + icin[4:]
        return prv
 
    def __init__( self, MMDDHHmmss='0101000000', step=1, self.reference=None ):
        # TO DO: check validity of MMDDHHmmss and reference
        self.MMDDHHmmss = MMDDHHmmss
        # step in integer number of years
        try:
            self.step = int(step)
        except ValueError:
            raise SystemExit( "ERROR: step " + step + " is not a valid integer." )
        self.reference = reference

    def next( self, icin ):
        # add step years (same MMDDHHmmss as year length varies)
        # TO DO: HANDLE years < 1000
        YYYY = icin[0:4]
        nxt = str(int(YYYY)+self.step) + icin[4:]
        return nxt

    def initial_adjust_up( self, icin ):
        # next or equal valid: equal as any year is valid
        ic = ct( icin )
        yr = str( int( ic.year ) + int( self.delay ))
        return ct( yr + self.MMDDHHmmss )

    def valid( self, ctime ):
        # Any valid cycle time is a valid year
        # TO DO: Or strictly valid (check MMDDHHmmss)?
        return True


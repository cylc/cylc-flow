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

class Anniversary( cylc.cycling.base.cycler ):

    @classmethod
    def offset( cls, icin, n ):
        # decrement n years (same MMDDHHmmss as year length varies)
        YYYY = icin[0:4]
        # TO DO: HANDLE years < 1000
        prv = str(int(YYYY)-int(n)) + icin[4:]
        return prv
 
    def __init__( self, MMDDHHmmss='0101000000', step=1, anchor=None ):
        # TO DO: check validity of MMDDHHmmss and anchor
        self.MMDDHHmmss = MMDDHHmmss
        # step in integer number of years
        try:
            self.step = int(step)
        except ValueError:
            raise SystemExit( "ERROR: step " + step + " is not a valid integer." )
        self.anchor = anchor

    def initial_adjust_up( self, icin ):
        # ADJUST UP TO THE NEXT VALID CYCLE (or not, if already valid).
        # Only used at suite start-up to find the first valid cycle at
        # or after the suite initial cycle time; in subsequent cycles
        # next() ensures we remain on valid cycles.

        foo = ct( icin )
        # first get MMDDHHmmss right
        if foo.MMDDHHmmss == self.MMDDHHmmss:
            # initial time is already valid
            pass
        else:
            # adjust up: must be suite start-up
            if foo.MMDDHHmmss < self.MMDDHHmmss:
                # round up
                foo.parse( foo.strvalue[0:4] + self.MMDDHHmmss )
            else:
                # round down and increment year
                # TO DO: HANDLE NON-FOUR-DIGIT-YEARS PROPERLY
                YYYY = str( int( foo.strvalue[0:4] ) + 1 )
                foo.parse( YYYY + self.MMDDHHmmss )

        # then adjust up relative to the anchor cycle and step
        if self.anchor:
            aYYYY = self.anchor[0:4] # TO DO: input error checking!
            YYYY = foo.strvalue[0:4]
            diff = int(aYYYY) - int(YYYY)
            rem = diff % self.step
            if rem > 0:
                n = self.step - rem
                YYYY = str( int( foo.strvalue[0:4] ) + n )
                foo.parse( YYYY + self.MMDDHHmmss )
            
        return foo.get()

    def next( self, icin ):
        # add step years (same MMDDHHmmss as year length varies)
        # TO DO: HANDLE years < 1000
        YYYY = icin[0:4]
        nxt = str(int(YYYY)+self.step) + icin[4:]
        return nxt

    def valid( self, ctime ):
        foo = ctime.get()
        res = True
        print "TO DO: FULL MMDDHHmmss in Anniversary.py"
        ###if foo[4:14] != self.MMDDHHmmss:
        print '>>>>>>>>>', foo[4:10], self.MMDDHHmmss[0:6]
        if foo[4:10] != self.MMDDHHmmss[0:6]:
            res = False
        elif self.anchor:
            aYYYY = self.anchor[0:4] # TO DO: input error checking!
            diff = int(aYYYY) - int(ctime.strvalue[0:4])
            rem = diff % self.step
            if rem != 0:
                res = False
        return res
 

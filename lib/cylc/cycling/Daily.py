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
 
    def __init__( self, HHmmss='000000', step=1, anchor=None ):
        # Check HH[mm[ss]]
        try:
            ct( '29990101' + HHmmss )
        except CycleTimeError:
            raise SystemExit( "ERROR, invalid HH[mm[ss]]: " + HHmmss )
        tmp = '000000'
        self.HHmmss = HHmmss + tmp[len(HHmmss):]

        # TO DO: check anchor
        self.anchor = anchor

        # Check step
        try:
            self.step = int( step )
        except ValueError:
            raise SystemExit( "ERROR: step must be a positive integer: " + step )
        if self.step <= 0:
            raise SystemExit( "ERROR: step must be a positive integer: " + step )

        # TO DO: what about half days etc.?

        # Set minimum runahead limit in hours
        self.minimum_runahead_limit = step * 24

    def initial_adjust_up( self, icin ):
        # ADJUST UP TO THE NEXT VALID CYCLE (or not, if already valid).
        # Only used at suite start-up to find the first valid cycle at
        # or after the suite initial cycle time; in subsequent cycles
        # next() ensures we remain on valid cycles.

        foo = ct( icin )
        # first get HHmmss right
        if foo.HHmmss == self.HHmmss:
            # initial time is already valid
            pass
        else:
            # adjust up: must be suite start-up
            if foo.HHmmss < self.HHmmss:
                # round up
                foo.parse( foo.strvalue[0:8] + self.HHmmss )
            else:
                # round down and increment by a day
                foo.parse( foo.strvalue[0:8] + self.HHmmss )
                foo.increment( days=1 )

        # then adjust up relative to the anchor cycle and step
        if self.anchor:
            diff = foo.subtract( ct(self.anchor) )
            rem = diff.days % self.step
            if rem > 0:
                n = self.step - rem
                foo.increment( days=n )
            
        return foo.get()

    def next( self, icin ):
        foo = ct(icin)
        foo.increment( days=self.step )
        return foo.get()

    def valid( self, ctime ):
        foo = ctime.get()
        res = True
        print "TO DO: FULL HHmmss in Daily.py"
        ###if foo[8:14] != self.HHmmss:
        if foo[8:10] != self.HHmmss[0:2]:
            res = False
        elif self.anchor:
            diff = ctime.subtract( ct(self.anchor) )
            rem = diff.days % self.step
            if rem != 0:
                res = False
        return res
 

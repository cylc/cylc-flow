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

from cylc.cycle_time import ct, CycleTimeError
from cylc.cycling.base import cycler, CyclerError

class Daily( cycler ):

    """For a cycle time sequence that increments by one or more days,
    with an anchor day so that the same sequence resultes regardless of
    initial cycle time.
    See lib/cylc/cycling/base.py for additional documentation."""

    @classmethod
    def offset( cls, T, n ):
        # decrement n days
        foo = ct(T)
        foo.decrement(days=int(n))
        return foo.get()

    def __init__( self, T=None, step=1 ):
        """Store HH, step, and anchor."""

        self.c_offset = 0

        # check input validity
        try:
            T = ct( T ).get()
        except CycleTimeError, x:
            raise CyclerError, str(x)
        else:
            # anchor day
            self.anchorYYYYMMDDHH = T
            self.anchorYYYYMMDD = T[0:8]
            self.HH = T[8:]

        # step in integer number of days
        try:
            # check validity
            self.step = int(step)
        except ValueError:
            raise CyclerError, "ERROR: step " + step + " is not a valid integer"
        if self.step <= 0:
            raise SystemExit( "ERROR: step must be a positive integer: " + step )

    def get_min_cycling_interval( self ):
        return 24 * self.step

    def get_offset( self ):
        return 24 * self.c_offset

    def initial_adjust_up( self, T ):
        """Adjust T up to the next valid cycle time if not already valid."""

        foo = ct( T )
        # first get HH right
        if foo.hour == self.HH:
            # initial time is already valid
            pass
        else:
            # adjust up: must be suite start-up
            if int(foo.hour) < int(self.HH):
                # round up
                foo.parse( foo.strvalue[0:8] + self.HH )
            else:
                # round down and increment by a day
                foo.parse( foo.strvalue[0:8] + self.HH )
                foo.increment( days=1 )

        # now adjust up to the next on-sequence cycle
        diff = ct(self.anchorYYYYMMDDHH).subtract( foo )
        rem = diff.days % self.step
        foo.increment( days=rem )

        return foo.get()

    def prev( self, T ):
        """Subtract step days to T."""
        foo = ct(T)
        foo.decrement( days=self.step )
        return foo.get()

    def next( self, T ):
        """Add step days to T."""
        foo = ct(T)
        foo.increment( days=self.step )
        return foo.get()

    def valid( self, CT ):
        """Is CT a member of my cycle time sequence?"""
        foo = CT.get()
        res = True
        if foo[8:10] != self.HH:
            # wrong HH
            res = False
        else:
            # right HH, check the day is valid
            diff = CT.subtract( ct(self.anchorYYYYMMDD) )
            rem = diff.days % self.step
            if rem != 0:
                res = False
        return res

    def adjust_state( self, offset ):
        foo = ct( self.anchorYYYYMMDD )
        foo.decrement( days=int(offset) )
        self.c_offset = int(offset)
        self.anchorYYYYMMDD = foo.get()[0:8]


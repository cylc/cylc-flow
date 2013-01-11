#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

import datetime
import calendar

from cylc.cycle_time import ct, CycleTimeError
from cylc.cycling.base import cycler, CyclerError

# add the years arithmetic routines to start with here, where they get used
# to keep the original design of the code as little as possible changed.

def sub_years(current_date, N):
    """Subtract N years from current_date; 
    works for positive or negative N."""
    start_date = current_date.get_datetime()
    year = start_date.year - N
    return ct (start_date.replace(year) )

def add_years(current_date, N):
    """Add N years to current_date; 
    works for positive or negative N."""
    return sub_years( current_date, -N )

class Yearly( cycler ):

    """For a cycle time sequence that increments by one or more years to
    the same anniversary date (e.g. every second year at 5 May 00 UTC)
    with an anchor year so that the same sequence results regardless of
    initial cycle time.
    See lib/cylc/cycling/base.py for additional documentation."""

    @classmethod
    def offset( cls, T, n ):
        """Decrement T by n years to the same MMDDHHmmss."""
        return sub_years( ct( T ), int(n) ).get()
 
    def __init__( self, T=None, step=1 ):
        """Store anniversary date, step, and anchor."""
        # check input validity
        try:
            T = ct( T ).get() # allows input of just YYYY
        except CycleTimeError, x:
            raise CyclerError, str(x)
        else:
            # anchor year
            self.anchorDate= T
            # aniversary date
            self.MMDDHHmmss = T[4:]
 
        # step in integer number of years
        try:
            # check validity
            self.step = int(step)
        except ValueError:
            raise CyclerError, "ERROR: step " + step + " is not a valid integer"
        if self.step <= 0:
            raise SystemExit( "ERROR: step must be a positive integer: " + step )

    def get_min_cycling_interval( self ):
        return 24 * 366 * self.step

    def initial_adjust_up( self, T ):
        """Adjust T up to the next valid cycle time if not already valid."""
        try:
            # is T a legal cycle time 
            ct(T)
        except CycleTimeError, x:
            raise CyclerError, str(x)

        # first get the anniversary date MMDDHHmmss right
        if T[4:] < self.MMDDHHmmss:
            # just round up
            T = T[0:4] + self.MMDDHHmmss
        elif T[4:] > self.MMDDHHmmss:
            # increment the year and round up
            T = add_years( ct( T ), 1 ).get()[0:4] + self.MMDDHHmmss
        else:
            # equal: no need to adjust
            pass

        # now adjust year up if necessary, according to anchor step
        diff = int(self.anchorDate[0:4]) - int(T[0:4])
        rem = diff % self.step
        if rem > 0:
            T = add_years( ct( T ), self.step - rem ).get()[0:4] + self.MMDDHHmmss

        return T

    def next( self, T ):
        """Add step years to get to the next anniversary after T."""
        return  add_years( ct( T ), self.step).get()

    def valid( self, current_date ):
        """Is current_date a member of my cycle time sequence?"""
        result = True
        T = current_date.get()

        if T[4:] != self.MMDDHHmmss:
            # wrong anniversary date
            result = False
        else:
            # right anniversary date, check the year is valid 
            diff = int(self.anchorDate[0:4]) - int(T[0:4])
            rem = diff % self.step
            if rem != 0:
                result = False

        return result

    def adjust_state( self, offset ):
        self.anchorDate = sub_years( ct(self.anchorDate), int(offset) ).get()

if __name__ == "__main__":
    # UNIT TEST

    inputs = [ \
            ('2010',), \
            ('2010080806',), \
            ('2010080806', 2), \
            ('2010080806', 3), \
            ('2010080806x', 2), \
            ('2010080806', 'x')] 

    for i in inputs:
        print i
        try:
            foo = Yearly( *i )
            print ' + next(1999):', foo.next('1999' )
            print ' + initial_adjust_up(2010080512):', foo.initial_adjust_up( '2010080512' )
            print ' + initial_adjust_up(2010090912):', foo.initial_adjust_up( '2010090912' )
            print ' + initial_adjust_up(2008040512):', foo.initial_adjust_up( '2008040512' )
            print ' + initial_adjust_up(' + str(i[0]) + '):', foo.initial_adjust_up( str(i[0]) ), '<should not change'
            print ' + valid(2012080806):', foo.valid( ct('2012080806') )
            print ' + valid(2011080806):', foo.valid( ct('2011080806') )
        except Exception, x:
            print ' !', x


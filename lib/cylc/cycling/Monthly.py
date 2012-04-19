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

import datetime
import calendar

from cylc.cycle_time import ct, CycleTimeError
from cylc.cycling.base import cycler, CyclerError

# add the months arithmetic routines to start with here, where they get used
# to keep the original design of the code as little as possible changed.

def add_months(current_date, months):

    start_date = current_date.get_datetime()

    year = start_date.year + (months / 12)
    month = start_date.month + (months % 12)
    day = start_date.day

    if month > 12:
        month = month % 12
        year = year + 1

    days_next = calendar.monthrange(year, month)[1]
    if day > days_next:
        day = days_next

    return  ct( start_date.replace(year, month, day) )

def sub_months(current_date, months):

    start_date = current_date.get_datetime()

    year = start_date.year
    month = start_date.month
    day = start_date.day

    month = month - months 
    if month <= 0:
        month = (11 + month) % 12 + 1
        year = year - 1

    days_next = calendar.monthrange(year, month)[1]
    if day > days_next:
        day = days_next

    return ct( start_date.replace(year, month, day) )

class Monthly( cycler ):

    """For a cycle time sequence that increments by one or more months to
    the same day in month (e.g. every second month at 5th  00 UTC)
    with an anchor date so that the same sequence results regardless of
    initial cycle time.
    See lib/cylc/cycling/base.py for additional documentation."""

    @classmethod
    def offset( cls, T, n ):
        """Decrement T by n months to the same DDHHmmss."""
        current_date = ct( T )
        return sub_months( current_date, n ).get()
 
    def __init__( self, T=None, step=1 ):
        """Store date, step, and anchor."""

       # check input validity
        try:
            T = ct( T ).get() # allows input of just YYYYMM
        except CycleTimeError, x:
            raise CyclerError, str(x)
        else:
            # anchor date
            self.anchorDate = T  
            # day of month and time
            self.DDHHmmss = T[6:]
 
        # step in integer number of months
        try:
            # check validity
            self.step = int(step)
        except ValueError:
            raise CyclerError, "ERROR: step " + step + " is not a valid integer"
        if self.step <= 0:
            raise SystemExit( "ERROR: step must be a positive integer: " + step )
        if self.step > 11:
            raise SystemExit( "ERROR: step must be a positive integer smaller than 12: " + step )

        # default minimum runahead limit in hours equals at least <step> years
        self.minimum_runahead_limit = 24 * 366 * self.step

    def initial_adjust_up( self, T ):
        """Adjust T up to the next valid cycle time if not already valid."""

        try:
            # is T a legal cycle time 
            ct( T )
        except CycleTimeError, x:
            raise CyclerError, str(x)

        # adjust up to next valid
        ta = 12 * int(self.anchorDate[0:4]) + int(self.anchorDate[4:6]) - 1
        tc = 12 * int(T[0:4]) + int(T[4:6]) - 1
        diff = abs( ta - tc )
        rem = diff % self.step
        adjusted_date  = add_months( ct( T ), rem ).get()

        # get monthly date DDHHmmss right
        if T[6:] != self.DDHHmmss:
            DDHHmmss = self.DDHHmmss
        else:
            DDHHmmss = T[6:]

        return adjusted_date[0:6] + DDHHmmss  

    def next( self, T ):
        """Add step years to get to the next anniversary after T."""
        current_date = ct(T)
        return  add_months(current_date, self.step).get()

    def valid( self, current_date ):
        """Is current_date a member of my cycle time sequence?"""
        result = True
        T = current_date.get()

        if T[6:] != self.DDHHmmss:
            # wrong anniversary date
            result = False
        else:
            # right anniversary date, check if the month is valid 
            ta = 12 * int(self.anchorDate[0:4]) + int(self.anchorDate[4:6]) - 1
            tc = 12 * int(T[0:4]) + int(T[4:6]) - 1
            diff = abs( ta - tc )
            rem = diff % self.step
            if rem != 0:
                result = False

        return result

if __name__ == "__main__":
    # UNIT TEST

    inputs = [ \
            ('197801',), \
            ('1978080806',), \
            ('1978080806', 2), \
            ('2078080806', 3), \
            ('1978080806x', 2), \
            ('1978080806', 'x')] 

    for i in inputs:
        try:
            foo = Monthly( *i )
            print ' + next(197801):' + foo.next('197801')
            print ' + initial_adjust_up(2010080512):', foo.initial_adjust_up( '2010080512' )
            print ' + initial_adjust_up(2010090512):', foo.initial_adjust_up( '2010090512' )
            print ' + initial_adjust_up(2078120512):', foo.initial_adjust_up( '2078120512' )
            print ' + valid(3012080806):', foo.valid( ct('3012080806') )
            print ' + valid(201108006):', foo.valid( ct('201108006') )
        except Exception, x:
            print ' ! ... ', x


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

def add_months(start_date, months):
    year = start_date.year + (months / 12)
    month = start_date.month + (months % 12)
    day = start_date.day

    if month > 12:
        month = month % 12
        year = year + 1

    days_next = calendar.monthrange(year, month)[1]
    if day > days_next:
        day = days_next

    return start_date.replace(year, month, day)

def sub_months(start_date, months):
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

    return start_date.replace(year, month, day)

class Monthly( cycler ):

    """For a cycle time sequence that increments by one or more months to
    the same day in month (e.g. every second month at 5th  00 UTC)
    with an anchor date so that the same sequence results regardless of
    initial cycle time.
    See lib/cylc/cycling/base.py for additional documentation."""

    @classmethod
    def offset( cls, T, n ):
        """Decrement T by n months to the same DDHHmmss."""
        YYYY = T[0:4]
        MMDDHHmmss = T[4:]
        return str(int(YYYY)-int(n)) + MMDDHHmmss
 
    def __init__( self, T=None, step=1 ):
        """Store date, step, and anchor."""
        # check input validity
        try:
            T = ct( T ).get() # allows input of just YYYYMM
        except CycleTimeError, x:
            raise CyclerError, str(x)
        else:
            # anchor year
            self.anchorYYYY = T[0:4]
            # aniversary date
            self.MMDDHHmmss = T[4:]
 
        # step in integer number of months
        try:
            # check validity
            self.step = int(step)
        except ValueError:
            raise CyclerError, "ERROR: step " + step + " is not a valid integer"
        if self.step <= 0:
            raise SystemExit( "ERROR: step must be a positive integer: " + step )

        # default minimum runahead limit in hours
        self.minimum_runahead_limit = 24 * 366 * self.step

    def initial_adjust_up( self, T ):
        """Adjust T up to the next valid cycle time if not already valid."""
        try:
            # is T a legal cycle time 
            ct(T)
        except CycleTimeError, x:
            raise CyclerError, str(x)

        # first get the anniversary date MMDDHHmmss right
        if T[4:] != self.MMDDHHmmss:
            # adjust up to next valid
            if T[4:] < self.MMDDHHmmss:
                # round up
                T = T[0:4] + self.MMDDHHmmss
            else:
                # round down and increment the year
                T = self.pad_year(int(T[0:4])+1) + self.MMDDHHmmss

        # now adjust up relative to the anchor cycle and step
        diff = int(self.anchorYYYY) - int(T[0:4])
        rem = diff % self.step
        if rem > 0:
            n = self.step - rem
            T = self.pad_year(int(T[0:4])+n) + self.MMDDHHmmss

        return T

    def next( self, T ):
        """Add step years to get to the next anniversary after T."""
        return self.pad_year( int(T[0:4])+self.step) + T[4:]

    def valid( self, CT ):
        """Is CT a member of my cycle time sequence?"""
        result = True
        T = CT.get()
        if T[4:10] != self.MMDDHHmmss[0:6]:
            # wrong anniversary date
            result = False
        else:
            # right anniversary date, check the year is valid 
            diff = int(self.anchorYYYY) - int(T[0:4])
            rem = diff % self.step
            if rem != 0:
                result = False
        return result

    def pad_year( self, iY ):
        # return string YYYY from an integer year value
        tmp = '0000' # template, to handle years < 1000
        s_iY = str( iY )
        n = len( s_iY )
        return tmp[n:] + s_iY[0:n]

if __name__ == "__main__":
    # UNIT TEST

    inputs = [ \
            ('2010',), \
            ('2010080806',), \
            ('2010080806', 2), \
            ('2010080806x', 2), \
            ('2010080806', 'x')] 

    for i in inputs:
        print i
        try:
            foo = Monthly( *i )
            print ' + next(1999):', foo.next('1999' )
            print ' + initial_adjust_up(2010080512):', foo.initial_adjust_up( '2010080512' )
            print ' + initial_adjust_up(2010090512):', foo.initial_adjust_up( '2010090512' )
            print ' + valid(2012080806):', foo.valid( ct('2012080806') )
            print ' + valid(201108006):', foo.valid( ct('2011080806') )
        except Exception, x:
            print ' !', x


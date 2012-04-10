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

from cylc.cycle_time import ct, CycleTimeError
from cylc.cycling.base import cycler, CyclerError

def pad_year( iY ):
    # return string YYYY from an integer year value
    tmp = '0000' # template, to handle years < 1000
    s_iY = str( iY )
    n = len( s_iY )
    return tmp[n:] + s_iY[0:n]

class Anniversary( cycler ):

    """For a cycle time sequence that increments by one or more years to
    the same anniversary date (e.g. every second year at 5 May 00 UTC)
    with an anchor year to pin the sequence down (so that the same
    sequence results regardless of the initial cycle time).
    See lib/cylc/cycling/base.py for additional documentation."""

    @classmethod
    def offset( cls, T, n, reverse ):
        """Decrement T by n years to the same MMDDHHmmss."""
        YYYY = T[0:4]
        MMDDHHmmss = T[4:]
        if reverse:
            return str(int(YYYY)+int(n)) + MMDDHHmmss
        else:
            return str(int(YYYY)-int(n)) + MMDDHHmmss
 
    def __init__( self, T=None, step=1 ):
        """Store anniversary date, step, and anchor."""
        # check input validity
        try:
            T = ct( T ).get() # allows input of just YYYY
        except CycleTimeError, x:
            raise CyclerError, str(x)
        else:
            # anchor year
            self.anchorYYYY = T[0:4]
            # aniversary date
            self.MMDDHHmmss = T[4:]
 
        # step in integer number of years
        try:
            # check validity
            self.step = int(step)
        except ValueError:
            raise CyclerError, "ERROR: step " + step + " is not a valid integer"

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
                T = pad_year(int(T[0:4])+1) + self.MMDDHHmmss

        # now adjust up relative to the anchor cycle and step
        diff = int(self.anchorYYYY) - int(T[0:4])
        rem = diff % self.step
        if rem > 0:
            n = self.step - rem
            T = pad_year(int(T[0:4])+n) + self.MMDDHHmmss
            
        return T

    def next( self, T ):
        """Add step years to get to the next anniversary after T."""
        return pad_year( int(T[0:4])+self.step) + T[4:]

    def valid( self, CT ):
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
            foo = Anniversary( *i )
            print ' + next(1999):', foo.next('1999' )
            print ' + adjust_up(2010080512):', foo.initial_adjust_up( '2010080512' )
            print ' + adjust_up(2010090512):', foo.initial_adjust_up( '2010090512' )
            print ' + valid(2012080806):', foo.valid( ct('2012080806') )
            print ' + valid(201108006):', foo.valid( ct('2011080806') )
        except Exception, x:
            print ' !', x




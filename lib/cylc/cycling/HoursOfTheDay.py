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

from cylc.cycle_time import ct
from cylc.cycling.base import cycler, CyclerError

class HoursOfTheDay( cycler ):

    """This implements cylc's original "hours of the day" NWP-style
    cycling: a task has a list of "valid hours", with 0 <= HH <= 23.
    Incrementing jumps to the next hour in the list, across day
    boundaries when necessary. Irregular lists are allowed: [0,3,6,23].
    See lib/cylc/cycling/base.py for additional documentation."""

    @classmethod
    def offset( cls, T, n ):
        # decrement n hours
        foo = ct(T)
        foo.decrement(hours=int(n))
        return foo.get()

    def __init__( self, *args ):
        """Parse and store incoming list of hours of the day."""
        self.c_offset = 0
        if len(args) == 0:
            # no args, assume all hours
            self.valid_hours = range(23)
        else:
            self.valid_hours = []
            for arg in args:
                if int(arg) < 0 or int(arg) > 23:
                    raise CyclerError, 'ERROR, HoursOfTheDay (0 << hour << 23) illegal hour: ' + str(arg)
                self.valid_hours.append( int(arg) )
            self.valid_hours.sort()

        # smallest interval between successive cycle times
        prev = self.valid_hours[0]
        sml = 24
        for h in self.valid_hours[1:]:
            diff = int(h) - int(prev)
            prev = h
            if diff < sml:
                sml = diff
        # now check the interval between the last and first valid
        # hours (i.e. crossing the day boundary).
        diff = 24 - prev + self.valid_hours[0]
        if diff < sml:
            sml = diff
        self.smallest_interval = sml

    def get_min_cycling_interval( self ):
        return self.smallest_interval

    def get_offset( self ):
        return self.c_offset

    def adjust_state( self, offset ):
        self.c_offset = int(offset)
        adj_hours = []
        for hour in self.valid_hours:
            adj = hour - self.c_offset
            # convert back to 0-23 range, e.g. 30 => 6, -30 => 18, ...
            adj_hours.append( adj % 24 )
        self.valid_hours = adj_hours
        self.valid_hours.sort()

    def initial_adjust_up( self, T ):
        """Adjust T up to the next valid cycle time if not already valid."""
        adjusted = ct( T )
        rh = int(adjusted.hour)
        incr = None
        for vh in self.valid_hours:
            if rh <= vh:
                incr = vh - rh
                break
        if incr == None:
            # rh is > last valid hour
            incr = 24 - rh + self.valid_hours[0]
        adjusted.increment( hours=incr )
        return adjusted.get()

    def adjust_dn( self, T ):
        """Adjust T down to the next valid cycle time if not already valid."""
        adjusted = ct( T )
        rh = int(adjusted.hour)
        decr = None
        for vh in reversed(self.valid_hours):
            if rh >= vh:
                decr = rh - vh
                break
        if decr == None:
            # vh is < first valid hour
            decr = 24 + rh - self.valid_hours[-1]
        adjusted.decrement( hours=decr )
        return adjusted.get()

    def next( self, T ):
        """Jump to the next valid hour in the list."""
        foo = ct(T)
        # cheat: add one hour and then call initial_adjust_up()
        foo.increment(hours=1)
        bar = self.initial_adjust_up(foo.get())
        return bar

    def prev( self, T ):
        """Jump to the previous valid hour in the list."""
        foo = ct(T)
        # cheat: decrement one hour and then call adjust_dn()
        foo.decrement(hours=1)
        bar = self.adjust_dn(foo.get())
        return bar


    def valid( self, CT ):
        """Return True if CT.hour is in my list of valid hours."""
        if int(CT.hour) in self.valid_hours:
            return True
        else:
            return False

if __name__ == "__main__":
    # UNIT TEST
    import sys

    inputs = [ \
            ('0','12'), \
            ('0','6','12','18'), \
            ('3', '6','9','12', '15', '18'), \
            ('3', '10','19'), \
            ('0', 'x')] 

    ctin = sys.argv[1]

    for i in inputs:
        print i
        try:
            foo = HoursOfTheDay( *i )
            print ' + prev, next:', foo.prev( ctin ), foo.next( ctin )
            #print ' + initial_adjust_up(2010080823):', foo.initial_adjust_up( '2010080823' )
            #print ' + valid(2012080900):', foo.valid( ct('2012080900') )
            #print ' + valid(201108019):', foo.valid( ct('2011080819') )
        except Exception, x:
            print ' !', x


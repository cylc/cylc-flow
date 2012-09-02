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
        if len(args) == 0:
            # no args, assume all hours
            self.valid_hours = range(0,23)
        else:
            self.valid_hours = []
            for arg in args:
                if int(arg) < 0 or int(arg) > 23:
                    raise CyclerError, 'ERROR, HoursOfTheDay (0 << hour << 23) illegal hour: ' + str(arg)
                self.valid_hours.append( int(arg) )
            self.valid_hours.sort()

        # default runahead limit in hours: twice the smallest interval between successive cycle times.
        prev = self.valid_hours[0]
        mrl = 24
        for h in self.valid_hours[1:]:
            diff = int(h) - int(prev)
            prev = h
            if diff < mrl:
                mrl = diff
        # now check the interval between the last and first valid
        # hours (i.e. crossing the day boundary).
        diff = 24 - prev + self.valid_hours[0]
        if diff < mrl:
            mrl = diff
        self.default_runahead_limit = mrl * 2

    def get_def_runahead( self ):
        return self.default_runahead_limit

    def adjust_state( self, offset ):
        adj_hours = []
        for hour in self.valid_hours:
            adj = hour - int(offset)
            if adj < 0:
                adj = 24 + adj
            adj_hours.append( adj )
        self.valid_hours = adj_hours

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
            incr = 24 - rh + self.valid_hours[0]
        adjusted.increment( hours=incr )
        return adjusted.get()

    def next( self, T ):
        """Jump to the next valid hour in the list."""
        foo = ct(T)
        # cheat: add one hour and then call initial_adjust_up()
        foo.increment(hours=1)
        bar = self.initial_adjust_up(foo.get())
        return bar

    def valid( self, CT ):
        """Return True if CT.hour is in my list of valid hours."""
        if int(CT.hour) in self.valid_hours:
            return True
        else:
            return False

if __name__ == "__main__":
    # UNIT TEST

    inputs = [ \
            ('0','12'), \
            ('0','6','12','18'), \
            ('3', '6','9','12', '15', '18'), \
            ('0', 'x')] 

    for i in inputs:
        print i
        try:
            foo = HoursOfTheDay( *i )
            print ' + next(2010080800):', foo.next('2010080800' )
            print ' + initial_adjust_up(2010080823):', foo.initial_adjust_up( '2010080823' )
            print ' + valid(2012080900):', foo.valid( ct('2012080900') )
            print ' + valid(201108019):', foo.valid( ct('2011080819') )
        except Exception, x:
            print ' !', x


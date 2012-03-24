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

class HoursOfTheDay( cylc.cycling.base.cycler ):

    @classmethod
    def offset( cls, icin, n ):
        # decrement n hours
        foo = ct(icin)
        foo.decrement( hours=n )
        return foo.get()

    def __init__( self, *args ):
        # TO DO: check arg validity (int and 0<arg<23)
        if len(args) == 0:
            self.valid_hours = range(0,23)
        else:
            self.valid_hours = []
            for arg in args:
                self.valid_hours.append( int(arg) )
            self.valid_hours.sort()

    def initial_adjust_up( self, icin ):
        # adjust up to the next valid hour
        adjusted = ct( icin )
        rh = int(adjusted.hour)
        incr = None
        for vh in self.valid_hours:
            if rh <= vh:
                incr = vh - rh
                break
        if incr == None:
            incr = 24 - rh + self.valid_hours[0]
        adjusted.increment( hours=incr )
        return adjusted

    def next( self, icin ):
        # add one hour
        ic = ct(icin)
        ic.increment(hours=1)
        # TO DO: STREAMLINE THIS SHIT:
        return self.initial_adjust_up(ic.get(Y2H=True)).get(Y2H=True)

    def valid( self, ctime ):
        # is ctime in this cycler's sequence
        # TO DO: int():
        if int(ctime.hour) in self.valid_hours:
            return True
        else:
            return False


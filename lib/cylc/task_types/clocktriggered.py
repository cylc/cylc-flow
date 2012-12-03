#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

import sys
import datetime
from cylc.cycle_time import ct

# TO DO: the task base class now has clock-triggering functionality too, to
# handle retry delays, so this class could probably disappear now to leave
# clock-triggering as just a special case of normal task initialization.

class clocktriggered(object):
    clock = None

    def is_clock_triggered( self ):
        return True

    def get_real_time_delay( self ):
        return self.real_time_delay

    def set_trigger_now( self, now=False ):
        self.trigger_now = now

    def start_time_reached( self ):
        if self.trigger_now:
            return True
        reached = False
        # check current time against expected start time
        rt = ct( self.c_time ).get_datetime()
        delayed_start = rt + datetime.timedelta( 0,0,0,0,0,self.real_time_delay,0 )
        current_time = clocktriggered.clock.get_datetime()
        if current_time >= delayed_start:
           reached = True
        return reached

    def ready_to_run( self ):
        # not ready unless delayed start time is up too.
        ready = False
        if self.state.is_currently('queued') or \
                self.state.is_currently('waiting') and self.prerequisites.all_satisfied():
            if self.start_time_reached():
                # We've reached the clock-trigger time
                if self.retry_delay_timer_start:
                    # A retry delay has been set ...
                    diff = clocktriggered.clock.get_datetime() - self.retry_delay_timer_start
                    foo = datetime.timedelta( 0,0,0,0,self.retry_delay,0,0 )
                    if diff >= foo:
                        # ... we've reached the retry delay time
                        ready = True
                else:
                    # no retry delay has been set
                    ready = True
            else:
                self.log( 'DEBUG', 'prerequisites satisfied but waiting on delayed start time' )
        return ready


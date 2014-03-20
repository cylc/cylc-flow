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

import sys
import datetime
from cylc.cycle_time import ct
from task import task
from cylc.wallclock import now

# TODO - the task base class now has clock-triggering functionality too, to
# handle retry delays, so this class could probably disappear now to leave
# clock-triggering as just a special case of normal task initialization.

class clocktriggered(object):
    clock = None

    is_clock_triggered = True

    def get_real_time_delay( self ):
        return self.real_time_delay

    def start_time_reached( self ):
        reached = False
        # check current time against expected start time
        rt = ct( self.c_time ).get_datetime()
        delayed_start = rt + datetime.timedelta( 0,0,0,0,0,self.real_time_delay,0 )
        if now() >= delayed_start:
           reached = True
        return reached

    def ready_to_run( self ):
        if task.ready_to_run( self ) and self.start_time_reached():
            #print '(ready)'
            return True
        else:
            #print '(not ready)'
            return False


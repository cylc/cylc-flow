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

import time
import cylc.cycling.iso8601
from isodatetime.timezone import get_local_time_zone
from task import task

# TODO - the task base class now has clock-triggering functionality too, to
# handle retry delays, so this class could probably disappear now to leave
# clock-triggering as just a special case of normal task initialization.

class clocktriggered(object):
    is_clock_triggered = True

    def start_time_reached( self ):
        reached = False
        if not hasattr(self, "point_as_seconds"):
            iso_timepoint = cylc.cycling.iso8601.point_parse(str(self.point))
            iso_clocktrigger_offset = cylc.cycling.iso8601.interval_parse(
                str(self.clocktrigger_offset))
            self.point_as_seconds = int(iso_timepoint.get(
                "seconds_since_unix_epoch"))
            self.clocktrigger_offset_as_seconds = int(
                iso_clocktrigger_offset.get_seconds())
            if iso_timepoint.time_zone.unknown:
                utc_offset_hours, utc_offset_minutes = (
                    get_local_time_zone())
                utc_offset_in_seconds = (
                    3600 * utc_offset_hours + 60 * utc_offset_minutes)
                self.point_as_seconds += utc_offset_in_seconds
            self.delayed_start = (self.point_as_seconds +
                    self.clocktrigger_offset_as_seconds)
            self.delayed_start_str = str(self.point + self.clocktrigger_offset)
        return time.time() > self.delayed_start

    def ready_to_run( self ):
        return task.ready_to_run(self) and self.start_time_reached()

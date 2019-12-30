#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""xtrigger function to check cycle point offset against the wall clock.

"""

from time import time
from cylc.cycling.iso8601 import interval_parse
from cylc.cylc_subproc import procopen


def wall_clock(offset=None, time_zone=None, point_as_seconds=None):
    """Return True if now > (point + offset) else False.

    If a time zone is provided, it must be a string available from terminal via
    the `timedatectl list-timezones` command. When used, this method will check
    for the current cycle point (plus the offset) adjusted to check as if the
    cycle point is for the provided time zone. The time zone functionality
    only works with suites with UTC cycle points as the xtrigger has no way of
    knowing the suites cycle point and has to assume it is in UTC.

    For example:
    offset=None, time_zone='America/New_York', cycle='20200101T0000Z'
    checks for for midnight on 1 Jan 2020 local New York time.

    offset=PT30M, time_zone='Australia/Melbourne', cycle='20200101T1200Z'
    checks for 1230PM on 1 Jan 2020 local Melbourne time.
    """

    if offset is None:
        offset_as_seconds = 0
    else:
        offset_as_seconds = int(interval_parse(offset).get_seconds())

    if time_zone is not None:
        # Obtain the time zone offset in the format +h:m
        # Do not use os.environ to adjust the TZ envar and time.tzset() to
        # obtain the time zone offset because that persists and could lead to
        # unexpected results
        tz_offset, _ = procopen(('date', '+%-:z'), env={'TZ': time_zone},
                                stdoutpipe=True).communicate()
        hours, mins = tz_offset.split(':')
        if hours[0] == '-':
            tz_seconds = int(hours) * 3600 - int(mins) * 60
        else:
            tz_seconds = int(hours) * 3600 + int(mins) * 60

        # Subtract the offset from point_as_seconds to adjust the point to be
        # mimicing the provided time zone
        point_as_seconds -= tz_seconds

    return time() > (point_as_seconds + offset_as_seconds)

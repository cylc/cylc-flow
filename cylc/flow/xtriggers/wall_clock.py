# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
from cylc.flow.cycling.iso8601 import interval_parse


def wall_clock(offset=None, absolute_as_seconds=None, point_as_seconds=None):
    """Return True if now > (point + offset) else False.

    Either provide an offset from the current cycle point *or* a wall-clock
    time.

    Args:
        offset (str):
            Satisfy this xtrigger after an offset from the current cycle point.
            Should be a duration in ISO8601 format.
        absolute_as_seconds (int):
            Satisfy this xtrigger after the specified time.
            Should be a datetime in the unix time format.
        point_as_seconds (int):
            Provided by Cylc. The cycle point in unix time format.

    """
    offset_as_seconds = 0
    if offset is not None:
        offset_as_seconds = int(interval_parse(offset).get_seconds())
    if absolute_as_seconds:
        trigger_time = absolute_as_seconds
    else:
        trigger_time = point_as_seconds + offset_as_seconds

    return time() > trigger_time

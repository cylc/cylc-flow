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
from cylc.flow.cycling.iso8601 import interval_parse


def wall_clock(offset=None, point_as_seconds=None):
    """Return True if now > (point + offset) else False."""
    if offset is None:
        offset_as_seconds = 0
    else:
        offset_as_seconds = int(interval_parse(offset).get_seconds())
    return time() > (point_as_seconds + offset_as_seconds)

# -*- coding: utf-8 -*-
#-----------------------------------------------------------------------------
# (C) British Crown Copyright 2013-2014 Met Office.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-----------------------------------------------------------------------------

"""This provides utilites for extracting the local time zone."""

import time


def get_local_time_zone():
    """Return the current local UTC offset in hours and minutes."""
    utc_offset_seconds = -time.timezone
    if time.localtime().tm_isdst == 1 and time.daylight:
        utc_offset_seconds = -time.altzone
    utc_offset_minutes = (utc_offset_seconds // 60) % 60
    utc_offset_hours = utc_offset_seconds // 3600
    return utc_offset_hours, utc_offset_minutes


def get_local_time_zone_format(extended_mode=False, reduced_mode=False):
    """Return a string denoting the current local UTC offset."""
    utc_offset_hours, utc_offset_minutes = get_local_time_zone()
    if utc_offset_hours == 0 and utc_offset_minutes == 0:
        return "Z"
    reduced_timezone_template = "%s%02d"
    timezone_template = "%s%02d%02d"
    if extended_mode:
        timezone_template = "%s%02d:%02d"
    sign = "-" if (utc_offset_hours < 0 or utc_offset_minutes < 0) else "+"
    if reduced_mode and utc_offset_minutes == 0:
        return reduced_timezone_template % (sign, abs(utc_offset_hours))
    return timezone_template % (
        sign, abs(utc_offset_hours), abs(utc_offset_minutes))

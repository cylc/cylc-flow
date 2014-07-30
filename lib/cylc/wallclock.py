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

import flags
from datetime import datetime, timedelta
from isodatetime.data import TimeInterval
from isodatetime.parsers import TimePointParser
from isodatetime.timezone import (
    get_local_time_zone_format, get_local_time_zone)

TIME_ZONE_STRING_LOCAL_BASIC = get_local_time_zone_format(reduced_mode=True)
TIME_ZONE_STRING_LOCAL_EXTENDED = get_local_time_zone_format(
    extended_mode=True, reduced_mode=True)
TIME_ZONE_STRING_UTC = "Z"
TIME_ZONE_LOCAL_UTC_OFFSET = get_local_time_zone()

DATE_TIME_FORMAT_BASIC = "%Y%m%dT%H%M%S"
DATE_TIME_FORMAT_BASIC_SUB_SECOND = "%Y%m%dT%H%M%S.%f"
DATE_TIME_FORMAT_EXTENDED = "%Y-%m-%dT%H:%M:%S"
DATE_TIME_FORMAT_EXTENDED_SUB_SECOND = "%Y-%m-%dT%H:%M:%S.%f"

RE_DATE_TIME_FORMAT_EXTENDED = (
    "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-][\d:]+)?")

TIME_FORMAT_BASIC = "%H%M%S"
TIME_FORMAT_BASIC_SUB_SECOND = "%H%M%S.%f"
TIME_FORMAT_EXTENDED = "%H:%M:%S"
TIME_FORMAT_EXTENDED_SUB_SECOND = "%H:%M:%S.%f"


def now(override_use_utc=None):
    """Return a datetime.datetime object representing the current time.

    Keyword arguments:
    override_use_utc (default None) - a boolean (or None) that, if
    True, gives the date and time in UTC. If False, it gives the date
    and time in the local time zone. If None, the flags.utc boolean is
    used.

    """
    if override_use_utc or (override_use_utc is None and flags.utc):
        return datetime.utcnow()
    else:
        return datetime.now()


def get_current_time_string(display_sub_seconds=False, override_use_utc=None,
                            use_basic_format=False, only_display_time=False,
                            no_display_time_zone=False):
    """Return a string representing the current system time.

    Keyword arguments:
    display_sub_seconds (default False) - a boolean that, if True,
    switches on microsecond reporting
    override_use_utc (default None) - a boolean (or None) that, if
    True, switches on utc time zone reporting. If False, it switches
    off utc time zone reporting (even if flags.utc is True). If None,
    the flags.utc boolean is used.
    use_basic_format (default False) - a boolean that, if True,
    represents the date/time without "-" or ":" delimiters. This is
    most useful for filenames where ":" may cause problems.
    only_display_time (default False) - a boolean that, if True, only
    represents the sub-day part of the date/time.
    no_display_time_zone (default False) - a boolean that, if True,
    means that the date/time representation is returned without a time
    zone.

    """
    date_time = now(override_use_utc=override_use_utc)
    return get_time_string(date_time, display_sub_seconds=display_sub_seconds,
                           override_use_utc=override_use_utc,
                           use_basic_format=use_basic_format,
                           only_display_time=only_display_time,
                           no_display_time_zone=no_display_time_zone)


def get_time_string(date_time, display_sub_seconds=False,
                    override_use_utc=None, use_basic_format=False,
                    only_display_time=False, no_display_time_zone=False,
                    date_time_is_local=False):
    """Return a string representing the current system time.

    Arguments:
    date_time - a datetime.datetime object.

    Keyword arguments:
    display_sub_seconds (default False) - a boolean that, if True,
    switches on microsecond reporting
    override_use_utc (default None) - a boolean (or None) that, if
    True, switches on utc time zone reporting. If False, it switches
    off utc time zone reporting (even if flags.utc is True). If None,
    the flags.utc boolean is used.
    use_basic_format (default False) - a boolean that, if True,
    represents the date/time without "-" or ":" delimiters. This is
    most useful for filenames where ":" may cause problems.
    only_display_time (default False) - a boolean that, if True, only
    represents the sub-day part of the date/time.
    no_display_time_zone (default False) - a boolean that, if True,
    means that the date/time representation is returned without a time
    zone.
    date_time_is_local - a boolean that, if True, indicates that
    the date_time argument object is in the local time zone, not UTC.

    """
    if override_use_utc or (override_use_utc is None and flags.utc):
        time_zone_string = TIME_ZONE_STRING_UTC
        if date_time_is_local:
            date_time = date_time - timedelta(
                hours=TIME_ZONE_LOCAL_UTC_OFFSET[0],
                minutes=TIME_ZONE_LOCAL_UTC_OFFSET[1]
            )
    elif use_basic_format:
        time_zone_string = TIME_ZONE_STRING_LOCAL_BASIC
    else:
        time_zone_string = TIME_ZONE_STRING_LOCAL_EXTENDED
    if only_display_time:
        if use_basic_format:
            date_time_format_string = TIME_FORMAT_BASIC
            if display_sub_seconds:
                date_time_format_string = TIME_FORMAT_BASIC_SUB_SECOND
        else:
            date_time_format_string = TIME_FORMAT_EXTENDED
        if display_sub_seconds:
            date_time_format_string = TIME_FORMAT_EXTENDED_SUB_SECOND
    elif use_basic_format:
        date_time_format_string = DATE_TIME_FORMAT_BASIC
        if display_sub_seconds:
            date_time_format_string = DATE_TIME_FORMAT_BASIC_SUB_SECOND
    else:
        date_time_format_string = DATE_TIME_FORMAT_EXTENDED
        if display_sub_seconds:
            date_time_format_string = DATE_TIME_FORMAT_EXTENDED_SUB_SECOND
    date_time_string = date_time.strftime(date_time_format_string)
    if no_display_time_zone:
        return date_time_string
    return date_time_string + time_zone_string


def get_time_string_from_unix_time(unix_time, display_sub_seconds=False,
                                   use_basic_format=False,
                                   only_display_time=False,
                                   no_display_time_zone=False):
    """Convert a unix timestamp into a local time zone datetime.datetime.

    Arguments:
    unix_time - an integer or float number of seconds since the Unix
    epoch.

    Keyword arguments:
    display_sub_seconds (default False) - a boolean that, if True,
    switches on microsecond reporting
    use_basic_format (default False) - a boolean that, if True,
    represents the date/time without "-" or ":" delimiters. This is
    most useful for filenames where ":" may cause problems.
    only_display_time (default False) - a boolean that, if True, only
    represents the sub-day part of the date/time.
    no_display_time_zone (default False) - a boolean that, if True,
    means that the date/time representation is returned without a time
    zone.

    """
    date_time = datetime.fromtimestamp(unix_time)
    return get_time_string(date_time,
                           display_sub_seconds=display_sub_seconds,
                           use_basic_format=use_basic_format,
                           override_use_utc=None,
                           only_display_time=only_display_time,
                           no_display_time_zone=no_display_time_zone,
                           date_time_is_local=True)


def get_unix_time_from_time_string(time_string):
    """Convert a time string into a unix timestemp."""
    parser = TimePointParser()
    time_point = parser.parse(time_string)
    return time_point.get("seconds_since_unix_epoch")


def get_seconds_as_interval_string(seconds):
    """Convert a number of seconds into an ISO 8601 duration string."""
    return str(TimeInterval(seconds=seconds, standardize=True))

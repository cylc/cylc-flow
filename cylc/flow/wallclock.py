# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
"""Wall clock related utilities."""

from calendar import timegm
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from metomi.isodatetime.timezone import (
    TimeZoneFormatMode,
    get_local_time_zone,
    get_local_time_zone_format,
)


DATE_TIME_FORMAT_BASIC = "%Y%m%dT%H%M%S"
DATE_TIME_FORMAT_BASIC_SUB_SECOND = "%Y%m%dT%H%M%S.%f"
DATE_TIME_FORMAT_EXTENDED = "%Y-%m-%dT%H:%M:%S"
DATE_TIME_FORMAT_EXTENDED_SUB_SECOND = "%Y-%m-%dT%H:%M:%S.%f"

_FLAGS = {r'utc_mode': False}

RE_DATE_TIME_FORMAT_EXTENDED = (
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-][\d:]+)?")

TIME_FORMAT_BASIC = "%H%M%S"
TIME_FORMAT_BASIC_SUB_SECOND = "%H%M%S.%f"
TIME_FORMAT_EXTENDED = "%H:%M:%S"
TIME_FORMAT_EXTENDED_SUB_SECOND = "%H:%M:%S.%f"

TIME_ZONE_STRING_UTC = "Z"
TIME_ZONE_UTC_UTC_OFFSET = (0, 0)

TIME_ZONE_LOCAL_INFO = {
    "hours": get_local_time_zone()[0],
    "minutes": get_local_time_zone()[1],
    "string_basic": get_local_time_zone_format(
        TimeZoneFormatMode.reduced),
    "string_extended": get_local_time_zone_format(
        TimeZoneFormatMode.extended)
}

TIME_ZONE_UTC_INFO = {
    "hours": TIME_ZONE_UTC_UTC_OFFSET[0],
    "minutes": TIME_ZONE_UTC_UTC_OFFSET[1],
    "string_basic": TIME_ZONE_STRING_UTC,
    "string_extended": TIME_ZONE_STRING_UTC
}

PARSER = None


def get_utc_mode():
    """Return value of UTC mode."""
    return _FLAGS['utc_mode']


def set_utc_mode(mode):
    """Set value of UTC mode."""
    _FLAGS['utc_mode'] = bool(mode)


def now(override_use_utc: bool | None = None) -> tuple[datetime, bool]:
    """Return a current-time, timezone-aware datetime.datetime and a flag
    indicating whether it is UTC or not.

    Keyword arguments:
    override_use_utc (default None) - a boolean (or None) that, if
    True, gives the date and time in UTC. If False, it gives the date
    and time in the local time zone. If None, the _FLAGS['utc_mode'] boolean is
    used.

    """
    if override_use_utc or (override_use_utc is None and _FLAGS['utc_mode']):
        return datetime.now(timezone.utc), False
    else:
        return datetime.now().astimezone(), True


def get_current_time_string(display_sub_seconds=False, override_use_utc=None,
                            use_basic_format=False):
    """Return a string representing the current system time.

    Keyword arguments:
    display_sub_seconds (default False) - a boolean that, if True,
    switches on microsecond reporting
    override_use_utc (default None) - a boolean (or None) that, if
    True, switches on utc time zone reporting. If False, it switches
    off utc time zone reporting (even if _FLAGS['utc_mode'] is True). If None,
    the _FLAGS['utc_mode'] boolean is used.
    use_basic_format (default False) - a boolean that, if True,
    represents the date/time without "-" or ":" delimiters. This is
    most useful for filenames where ":" may cause problems.

    """
    date_time, date_time_is_local = now(override_use_utc=override_use_utc)
    return get_time_string(date_time, display_sub_seconds=display_sub_seconds,
                           override_use_utc=override_use_utc,
                           date_time_is_local=date_time_is_local,
                           use_basic_format=use_basic_format)


def get_time_string(
    date_time: datetime,
    display_sub_seconds: bool = False,
    override_use_utc: bool | None = None,
    use_basic_format: bool = False,
    date_time_is_local: bool = False,
    custom_time_zone_info: dict | None = None,
):
    """Return a string representing the current system time.

    Args:
        date_time: Datetime to operate on.
        display_sub_seconds:
            Switch on microsecond reporting.
        override_use_utc:
            Switch on utc time zone reporting.
            If False, it switches off utc time zone reporting even
            if ``_FLAGS['utc_mode']`` is True).
            If None, the ``_FLAGS['utc_mode']`` boolean is used.
        use_basic_format:
            Represent the date/time without "-" or ":"
            delimiters. This is useful for filenames, where ":" may
            cause problems.
        date_time_is_local:
            Indicates that the date_time argument
            object is in the local time zone, not UTC.
        custom_time_zone_info:
            A dictionary that enforces a particular time zone:

            .. code-block:: python
                {
                    "hours": _hours,           # offset from UTC
                    "minutes": _minutes,       # offset from utc
                    "string_basic": _string,    # timezone designators
                    "string_extened": _string
                }

            Usage of ``string_basic`` or ``string_extended`` is
            switched by ``use_basic_format``.

    """
    time_zone_string = None
    local_tz = get_local_time_zone()
    if custom_time_zone_info is not None:
        custom_hours = custom_time_zone_info["hours"]
        custom_minutes = custom_time_zone_info["minutes"]
        if use_basic_format:
            custom_string = custom_time_zone_info["string_basic"]
        else:
            custom_string = custom_time_zone_info["string_extended"]
        if date_time_is_local:
            date_time_hours, date_time_minutes = local_tz
        else:
            date_time_hours, date_time_minutes = (0, 0)
        diff_hours = custom_hours - date_time_hours
        diff_minutes = custom_minutes - date_time_minutes
        date_time = date_time + timedelta(
            hours=diff_hours, minutes=diff_minutes)
        time_zone_string = custom_string
    elif override_use_utc or (override_use_utc is None and _FLAGS['utc_mode']):
        time_zone_string = TIME_ZONE_STRING_UTC
        if date_time_is_local:
            date_time = date_time - timedelta(
                hours=local_tz[0],
                minutes=local_tz[1]
            )
    else:
        if use_basic_format:
            time_zone_string = get_local_time_zone_format(
                TimeZoneFormatMode.reduced)
        else:
            time_zone_string = get_local_time_zone_format(
                TimeZoneFormatMode.extended)
        if not date_time_is_local:
            diff_hours, diff_minutes = local_tz
            date_time = date_time + timedelta(
                hours=diff_hours, minutes=diff_minutes)
    if use_basic_format:
        date_time_format_string = DATE_TIME_FORMAT_BASIC
        if display_sub_seconds:
            date_time_format_string = DATE_TIME_FORMAT_BASIC_SUB_SECOND
    else:
        date_time_format_string = DATE_TIME_FORMAT_EXTENDED
        if display_sub_seconds:
            date_time_format_string = DATE_TIME_FORMAT_EXTENDED_SUB_SECOND
    date_time_string = date_time.strftime(date_time_format_string)
    return date_time_string + time_zone_string


def get_time_string_from_unix_time(unix_time, display_sub_seconds=False,
                                   use_basic_format=False,
                                   custom_time_zone_info=None):
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
    custom_time_zone_info (default None) - a dictionary that enforces
    a particular time zone. It looks like {"hours": _hours,
    "minutes": _minutes, "string": _string} where _hours and _minutes
    are the hours and minutes offset from UTC and _string is the string
    to use as the time zone designator.

    """
    date_time = datetime.fromtimestamp(unix_time, timezone.utc)
    return get_time_string(date_time,
                           display_sub_seconds=display_sub_seconds,
                           use_basic_format=use_basic_format,
                           override_use_utc=None,
                           date_time_is_local=False,
                           custom_time_zone_info=custom_time_zone_info)


def get_unix_time_from_time_string(datetime_string):
    """Convert a datetime string into a unix timestamp.

    The datetime_string must match DATE_TIME_FORMAT_EXTENDED above,
    which is the extended ISO 8601 year-month-dayThour:minute:second format,
    plus a valid ISO 8601 time zone. For example, 2016-09-07T11:21:00+01:00,
    2016-12-25T06:00:00Z, or 2016-12-25T06:00:00+13.

    isodatetime is not used to do the whole parsing, partly for performance,
    but mostly because the calendar may be in non-Gregorian mode.

    """
    try:
        date_time_utc = datetime.strptime(
            datetime_string, DATE_TIME_FORMAT_EXTENDED + "Z")
    except ValueError:
        global PARSER
        if PARSER is None:
            from metomi.isodatetime.parsers import TimePointParser
            PARSER = TimePointParser()
        time_zone_info = PARSER.get_info(datetime_string)[1]
        time_zone_hour = int(time_zone_info["time_zone_hour"])
        time_zone_minute = int(time_zone_info.get("time_zone_minute", 0))
        offset_seconds = 3600 * time_zone_hour + 60 * time_zone_minute
        if "+" in datetime_string:
            datetime_string = datetime_string.split("+")[0]
        else:
            datetime_string = datetime_string.rsplit("-", 1)[0]
        date_time = datetime.strptime(
            datetime_string, DATE_TIME_FORMAT_EXTENDED)
        date_time_utc = date_time - timedelta(seconds=offset_seconds)
    return timegm(date_time_utc.timetuple())


def get_seconds_as_interval_string(seconds):
    """Convert a number of seconds into an ISO 8601 duration string."""
    from metomi.isodatetime.data import Duration
    return str(Duration(seconds=seconds, standardize=True))

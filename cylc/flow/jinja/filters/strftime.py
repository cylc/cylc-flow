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
"""Provides a Jinja2 filter for formatting ISO8601 datetime strings."""

from isodatetime.parsers import TimePointParser


def strftime(iso8601_datetime, strftime_str, strptime_str=None):
    """Format an iso8601 datetime string using an strftime string.

    Args:
        iso8601_datetime (str): Any valid ISO8601 datetime as a string.
        strftime_str (str): A valid strftime string to format the output
            datetime.
        strptime_str (str - optional): A valid strptime string defining the
            format of the provided iso8601_datetime.

    Return:
        The result of applying the strftime to the iso8601_datetime as parsed
        by the strptime string if provided.

    Raises:
        ISO8601SyntaxError: In the event of an invalid datetime string.
        StrftimeSyntaxError: In the event of an invalid strftime string.

    Examples:
        >>> # Basic usage.
        >>> strftime('2000-01-01T00Z', '%H')
        '00'
        >>> strftime('2000', '%H')
        '00'
        >>> strftime('2000', '%Y/%m/%d %H:%M:%S')
        '2000/01/01 00:00:00'
        >>> strftime('10661014T08+01', '%z')  # Timezone offset.
        '+0100'
        >>> strftime('10661014T08+01', '%j')  # Day of the year
        '287'

        >>> # Strptime.
        >>> strftime('12,30,2000', '%m', '%m,%d,%Y')
        '12'
        >>> strftime('1066/10/14 08:00:00', '%Y%m%dT%H', '%Y/%m/%d %H:%M:%S')
        '10661014T08'

        >>> # Exceptions.
        >>> strftime('invalid', '%H')  # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        <class 'isodatetime.parsers.ISO8601SyntaxError'>
        isodatetime.parsers.ISO8601SyntaxError: Invalid ISO 8601 date \
        representation: invalid
        >>> strftime('2000', '%invalid')  # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        isodatetime.parser_spec.StrftimeSyntaxError: Invalid \
        strftime/strptime representation: %i
        >>> strftime('2000', '%Y', '%invalid')
        ... # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        isodatetime.parser_spec.StrftimeSyntaxError: Invalid \
        strftime/strptime representation: %i
    """
    if not strptime_str:
        return TimePointParser().parse(iso8601_datetime).strftime(strftime_str)
    return TimePointParser().strptime(iso8601_datetime, strptime_str).strftime(
        strftime_str)

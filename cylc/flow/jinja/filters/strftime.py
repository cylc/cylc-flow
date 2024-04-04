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
"""Filter for formatting ISO8601 datetime strings."""

from typing import Optional

from metomi.isodatetime.parsers import TimePointParser


def strftime(
    iso8601_datetime: str,
    strftime_str: str,
    strptime_str: Optional[str] = None,
):
    """Format an :term:`ISO8601 datetime` string using an strftime string.

    .. code-block:: cylc

       {{ '10661004T08+01' | strftime('%H') }}  # 00

    It is also possible to parse non-standard date-time strings by passing a
    strptime string as the second argument.

    Args:
        iso8601_datetime:
            Any valid ISO8601 datetime as a string.
        strftime_str:
            A valid strftime string to format the output datetime.
        strptime_str:
            A valid strptime string defining the format of the provided
            iso8601_datetime.

    Return:
        The result of applying the strftime to the iso8601_datetime as parsed
        by the strptime string if provided.

    Raises:
        ISO8601SyntaxError: In the event of an invalid datetime string.
        StrftimeSyntaxError: In the event of an invalid strftime string.

    Python Examples:
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
        <class 'metomi.isodatetime.exceptions.ISO8601SyntaxError'>
        metomi.isodatetime.exceptions.ISO8601SyntaxError: Invalid ISO 8601 \
        date representation: invalid
        >>> strftime('2000', '%invalid')  # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        metomi.isodatetime.exceptions.StrftimeSyntaxError: Invalid \
        strftime/strptime representation: %i
        >>> strftime('2000', '%Y', '%invalid')
        ... # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        metomi.isodatetime.exceptions.StrftimeSyntaxError: Invalid \
        strftime/strptime representation: %i

    Jinja2 Examples:
        .. code-block:: cylc

           {% set START_CYCLE = '10661004T08+01' %}

           {{START_CYCLE | strftime('%Y')}}  # 1066
           {{START_CYCLE | strftime('%m')}}  # 10
           {{START_CYCLE | strftime('%d')}}  # 14
           {{START_CYCLE | strftime('%H:%M:%S %z')}}  # 08:00:00 +01
           {{'12,30,2000' | strftime('%m', '%m,%d,%Y')}}  # 12

    """
    if not strptime_str:
        return TimePointParser().parse(iso8601_datetime).strftime(strftime_str)
    return TimePointParser().strptime(iso8601_datetime, strptime_str).strftime(
        strftime_str)

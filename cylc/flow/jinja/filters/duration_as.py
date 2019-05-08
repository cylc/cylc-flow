# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA
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
"""Provides a Jinja2 filter for formatting ISO8601 duration strings."""

from isodatetime.parsers import DurationParser

SECONDS_PER_MINUTE = 60.0
MINUTES_PER_HOUR = 60.0
HOURS_PER_DAY = 24.0
DAYS_PER_WEEK = 7.0

SECONDS_PER_HOUR = SECONDS_PER_MINUTE * MINUTES_PER_HOUR
SECONDS_PER_DAY = SECONDS_PER_HOUR * HOURS_PER_DAY
SECONDS_PER_WEEK = SECONDS_PER_DAY * DAYS_PER_WEEK

CONVERSIONS = {
    ('s', 'seconds'): float,
    ('m', 'minutes'): lambda s: float(s) / SECONDS_PER_MINUTE,
    ('h', 'hours'): lambda s: float(s) / SECONDS_PER_HOUR,
    ('d', 'days'): lambda s: float(s) / SECONDS_PER_DAY,
    ('w', 'weeks'): lambda s: float(s) / SECONDS_PER_WEEK,
}


def duration_as(iso8601_duration, units):
    """Format an iso8601 duration string as the specified units.

    Args:
        iso8601_duration (str): Any valid ISO8601 duration as a string.
        units (str): Destination unit for the duration conversion

    Return:
        The total number of the specified unit contained in the specified
        duration as a floating-point number.

    Raises:
        ISO8601SyntaxError: In the event of an invalid datetime string.

    Examples:
        >>> # Basic usage.
        >>> duration_as('PT1M', 's')
        60.0
        >>> duration_as('PT1H', 'seconds')
        3600.0

        >>> # Exceptions.
        >>> duration_as('invalid', 's')  # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        isodatetime.parsers.ISO8601SyntaxError: Invalid ISO 8601 duration \
        representation: invalid
    """
    for converter_names in CONVERSIONS:
        if units.lower() in converter_names:
            converter = CONVERSIONS[converter_names]
            break
    else:
        raise ValueError('No matching units found for %s' % units)
    return converter(DurationParser().parse(iso8601_duration).get_seconds())


if __name__ == "__main__":
    for duration in ['PT1H', 'P1D', 'P7D']:
        for short_name, _ in CONVERSIONS:
            print(short_name, duration_as(duration, short_name))
        print('\n')

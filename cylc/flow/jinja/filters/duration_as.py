# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
"""Filter for formatting ISO8601 duration strings."""

from typing import Callable, Dict, Tuple

from metomi.isodatetime.parsers import DurationParser

SECONDS_PER_MINUTE = 60.0
MINUTES_PER_HOUR = 60.0
HOURS_PER_DAY = 24.0
DAYS_PER_WEEK = 7.0

SECONDS_PER_HOUR = SECONDS_PER_MINUTE * MINUTES_PER_HOUR
SECONDS_PER_DAY = SECONDS_PER_HOUR * HOURS_PER_DAY
SECONDS_PER_WEEK = SECONDS_PER_DAY * DAYS_PER_WEEK

CONVERSIONS: Dict[Tuple[str, str], Callable] = {
    ('s', 'seconds'): float,
    ('m', 'minutes'): lambda s: float(s) / SECONDS_PER_MINUTE,
    ('h', 'hours'): lambda s: float(s) / SECONDS_PER_HOUR,
    ('d', 'days'): lambda s: float(s) / SECONDS_PER_DAY,
    ('w', 'weeks'): lambda s: float(s) / SECONDS_PER_WEEK,
}


def duration_as(iso8601_duration: str, units: str) -> float:
    """Format an :term:`ISO8601 duration` string as the specified units.

    Units for the conversion can be specified in a case-insensitive short or
    long form:

    - Seconds - "s" or "seconds"
    - Minutes - "m" or "minutes"
    - Hours - "h" or "hours"
    - Days - "d" or "days"
    - Weeks - "w" or "weeks"

    While the filtered value is a floating-point number, it is often required
    to supply an integer to workflow entities (e.g. environment variables) that
    require it.  This is accomplished by chaining filters:

    - ``{{CYCLE_INTERVAL | duration_as('h') | int}}`` - 24
    - ``{{CYCLE_SUBINTERVAL | duration_as('h') | int}}`` - 0
    - ``{{CYCLE_INTERVAL | duration_as('s') | int}}`` - 86400
    - ``{{CYCLE_SUBINTERVAL | duration_as('s') | int}}`` - 1800

    Args:
        iso8601_duration: Any valid ISO8601 duration as a string.
        units: Destination unit for the duration conversion

    Return:
        The total number of the specified unit contained in the specified
        duration as a floating-point number.

    Raises:
        ISO8601SyntaxError: In the event of an invalid datetime string.

    Python Examples:
        >>> # Basic usage.
        >>> duration_as('PT1M', 's')
        60.0
        >>> duration_as('PT1H', 'seconds')
        3600.0

        >>> # Exceptions.
        >>> duration_as('invalid value', 's')  # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        metomi.isodatetime.exceptions.ISO8601SyntaxError: Invalid ISO 8601\
        duration representation: invalid value
        >>> duration_as('invalid unit', '#')  # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        ValueError: No matching units found for #

    Jinja2 Examples:
       .. code-block:: cylc

          {% set CYCLE_INTERVAL = 'PT1D' %}
          {{ CYCLE_INTERVAL | duration_as('h') }}  # 24.0
          {% set CYCLE_SUBINTERVAL = 'PT30M' %}
          {{ CYCLE_SUBINTERVAL | duration_as('hours') }}  # 0.5
          {% set CYCLE_INTERVAL = 'PT1D' %}
          {{ CYCLE_INTERVAL | duration_as('s') }}  # 86400.0
          {% set CYCLE_SUBINTERVAL = 'PT30M' %}
          {{ CYCLE_SUBINTERVAL | duration_as('seconds') }}  # 1800.0

    """
    for converter_names in CONVERSIONS:
        if units.lower() in converter_names:
            converter = CONVERSIONS[converter_names]
            break
    else:
        raise ValueError('No matching units found for %s' % units)
    return converter(DurationParser().parse(iso8601_duration).get_seconds())

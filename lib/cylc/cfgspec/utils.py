#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Utilities for configuration settings that are time intervals."""

from isodatetime.data import Calendar
from isodatetime.parsers import DurationParser
from parsec.util import itemstr
from parsec.validate import (
    _strip_and_unquote, _strip_and_unquote_list, _expand_list,
    IllegalValueError
)
from cylc.wallclock import get_seconds_as_interval_string

CALENDAR = Calendar.default()
DURATION_PARSER = DurationParser()


class DurationFloat(float):
    """Duration in seconds."""

    def __str__(self):
        return get_seconds_as_interval_string(self)


def coerce_interval(value, keys, _):
    """Coerce an ISO 8601 interval (or number: back-comp) into seconds."""
    value = _strip_and_unquote(keys, value)
    if not value:
        # Allow explicit empty values.
        return None
    try:
        interval = DURATION_PARSER.parse(value)
    except ValueError:
        raise IllegalValueError("ISO 8601 interval", keys, value)
    days, seconds = interval.get_days_and_seconds()
    return DurationFloat(days * CALENDAR.SECONDS_IN_DAY + seconds)


def coerce_interval_list(value, keys, args):
    """Coerce a list of intervals (or numbers: back-comp) into seconds."""
    return _expand_list(
        _strip_and_unquote_list(keys, value),
        keys,
        lambda v: coerce_interval(v, keys, args),
        True
    )

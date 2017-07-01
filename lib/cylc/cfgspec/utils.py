#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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

import re
from isodatetime.data import Calendar
from isodatetime.parsers import DurationParser
from parsec.validate import (
    _strip_and_unquote, _strip_and_unquote_list, _expand_list,
    IllegalValueError)
from cylc.mp_pool import SuiteFuncContext
from cylc.wallclock import get_seconds_as_interval_string

CALENDAR = Calendar.default()
DURATION_PARSER = DurationParser()

# Function name and args: "fname(args):PT10S".
RE_TRIG_FUNC = re.compile(r'(\w+)\((.*)\)(?:\:(\w+))?')


class DurationFloat(float):
    """Duration in seconds."""
    def __str__(self):
        return get_seconds_as_interval_string(self)


def get_interval_as_seconds(intvl, keys=None):
    """Convert an ISO 8601 interval to seconds."""
    if keys is None:
        keys = []
    try:
        interval = DURATION_PARSER.parse(intvl)
    except ValueError:
        raise IllegalValueError("ISO 8601 interval", keys, intvl)
    days, seconds = interval.get_days_and_seconds()
    return days * CALENDAR.SECONDS_IN_DAY + seconds


def coerce_interval(value, keys, _):
    """Coerce an ISO 8601 interval (or number: back-comp) into seconds."""
    value = _strip_and_unquote(keys, value)
    if not value:
        # Allow explicit empty values.
        return None
    return DurationFloat(get_interval_as_seconds(value, keys))


def coerce_interval_list(value, keys, args):
    """Coerce a list of intervals (or numbers: back-comp) into seconds."""
    return _expand_list(
        _strip_and_unquote_list(keys, value),
        keys,
        lambda v: coerce_interval(v, keys, args),
        True
    )


def coerce_xtrig(value, keys, _):
    """Coerce a string into an xtrigger function context object.

    Input example: "func_name(arg1=val1, arg2=val2, ...)".
    Checks for legal string templates in arg values too.

    """

    # TODO - DO A VALIDATION-TIME GET_FUNC, FOR SAFETY.

    label = keys[-1]
    value = _strip_and_unquote(keys, value)
    if not value:
        raise IllegalValueError("xtrigger", keys, value)
    fctx = None
    fname = None
    kwargs = {}
    m = RE_TRIG_FUNC.match(value)
    if m is None:
        raise IllegalValueError("xtrigger", keys, value)
    fname, fargs, intvl = m.groups()
    if intvl is None:
        # Default xtrigger interval 10 seconds.
        intvl = 'PT10S'
    seconds = float(coerce_interval(intvl, keys, None))

    if fargs:
        # Extract kwargs.
        for farg in re.split('\s*,\s*', fargs):
            key, val = re.split('\s*=\s*', farg)
            key = key.strip()
            kwargs[key] = _strip_and_unquote([key], val)

    fctx = SuiteFuncContext(label, fname, kwargs, seconds)
    return fctx

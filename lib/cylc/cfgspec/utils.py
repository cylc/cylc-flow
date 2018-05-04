#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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


DEFAULT_XTRIG_INTVL_SECS = '10'


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


def convert_range_list(values, keys):
    """Convert valid 'X .. Y' string to list of integers from X to Y inclusive.

    Return the list object or None if input is invalid 'X .. Y' format."""
    list_format = r'\s*(\d+)\s\.\.\s(\d+)\s*$'
    matches = re.match(list_format, values)
    core_err_msg = "Cannot extract start and end integers from '%s'" % values
    if not matches:
        raise ValueError(core_err_msg)
    try:
        list_start, list_end = matches.group(1, 2)
        startpoint = int(list_start)
        # Range function has non-inclusive end-point so must add 1.
        endpoint = int(list_end) + 1
        if startpoint >= endpoint:
            raise ValueError("%s >= %s but 'X .. Y' format requires X < Y." %
                             (startpoint, endpoint))
    except (AttributeError, TypeError):
        raise ValueError(core_err_msg)
    return range(startpoint, endpoint)


def coerce_range_list(value, keys, _):
    """Coerce a valid 'X .. Y' string into a list of integers."""
    return convert_range_list(value, keys)


def coerce_xtrig(value, keys, _):
    """Coerce a string into an xtrigger function context object.

    func_name(*func_args, **func_kwargs)
    Checks for legal string templates in arg values too.

    """

    def coerce_type(in_str):
        """Convert in_str to int, float, or bool, if possible."""
        try:
            val = int(in_str)
        except ValueError:
            try:
                val = float(in_str)
            except ValueError:
                if in_str == 'False':
                    val = False
                elif in_str == 'True':
                    val = True
                else:
                    # Leave as string.
                    val = _strip_and_unquote([], in_str)
        return val

    label = keys[-1]
    value = _strip_and_unquote(keys, value)
    if not value:
        raise IllegalValueError("xtrigger", keys, value)
    fname = None
    args = []
    kwargs = {}
    m = RE_TRIG_FUNC.match(value)
    if m is None:
        raise IllegalValueError("xtrigger", keys, value)
    fname, fargs, intvl = m.groups()
    if intvl is None:
        seconds = DEFAULT_XTRIG_INTVL_SECS
    else:
        seconds = float(coerce_interval(intvl, keys, None))

    if fargs:
        # Extract function args and kwargs.
        for farg in re.split(r'\s*,\s*', fargs):
            try:
                key, val = re.split(r'\s*=\s*', farg)
            except ValueError:
                args.append(coerce_type(farg.strip()))
            else:
                kwargs[key.strip()] = coerce_type(val)

    return SuiteFuncContext(label, fname, args, kwargs, seconds)

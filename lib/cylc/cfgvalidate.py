#!/usr/bin/env python3

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
"""Extend parsec.validate for Cylc configuration.

Coerce more value type from string (to time point, duration, xtriggers, etc.).
"""

import re

from isodatetime.data import Calendar, Duration, TimePoint
from isodatetime.dumpers import TimePointDumper
from isodatetime.parsers import DurationParser, TimePointParser
from parsec.validate import ParsecValidator, IllegalValueError

from cylc.subprocctx import SubFuncContext


class DurationFloat(float):
    """Duration in floating point seconds, but stringify as ISO8601 format."""

    def __str__(self):
        return str(Duration(seconds=self, standardize=True))


class CylcConfigValidator(ParsecValidator):
    """Type validator and coercer for Cylc configurations.

    Attributes:
        .coercers (dict):
            Map value type keys with coerce methods.
    """
    # Parameterized names containing at least one comma.
    _REC_NAME_SUFFIX = re.compile(r'\A[\w\-+%@]+\Z')
    _REC_TRIG_FUNC = re.compile(r'(\w+)\((.*)\)(?::(\w+))?')

    # Value type constants
    V_CYCLE_POINT = 'V_CYCLE_POINT'
    V_CYCLE_POINT_FORMAT = 'V_CYCLE_POINT_FORMAT'
    V_CYCLE_POINT_TIME_ZONE = 'V_CYCLE_POINT_TIME_ZONE'
    V_INTERVAL = 'V_INTERVAL'
    V_INTERVAL_LIST = 'V_INTERVAL_LIST'
    V_PARAMETER_LIST = 'V_PARAMETER_LIST'
    V_XTRIGGER = 'V_XTRIGGER'

    def __init__(self):
        ParsecValidator.__init__(self)
        self.coercers.update({
            self.V_CYCLE_POINT: self.coerce_cycle_point,
            self.V_CYCLE_POINT_FORMAT: self.coerce_cycle_point_format,
            self.V_CYCLE_POINT_TIME_ZONE: self.coerce_cycle_point_time_zone,
            self.V_INTERVAL: self.coerce_interval,
            self.V_INTERVAL_LIST: self.coerce_interval_list,
            self.V_PARAMETER_LIST: self.coerce_parameter_list,
            self.V_XTRIGGER: self.coerce_xtrigger,
        })

    @classmethod
    def coerce_cycle_point(cls, value, keys):
        """Coerce value to a cycle point."""
        if not value:
            return None
        value = cls.strip_and_unquote(keys, value)
        if value == 'now':
            # Handle this later in config.py when the suite UTC mode is known.
            return value
        if "next" in value or "previous" in value:
            # Handle this later, as for "now".
            return value
        if value.isdigit():
            # Could be an old date-time cycle point format, or integer format.
            return value
        if "P" not in value and (
                value.startswith('-') or value.startswith('+')):
            # We don't know the value given for num expanded year digits...
            for i in range(1, 101):
                try:
                    TimePointParser(num_expanded_year_digits=i).parse(value)
                except ValueError:
                    continue
                return value
            raise IllegalValueError('cycle point', keys, value)
        if "P" in value:
            # ICP is an offset
            parser = DurationParser()
            try:
                if value.startswith("-"):
                    # parser doesn't allow negative duration with this setup?
                    parser.parse(value[1:])
                else:
                    parser.parse(value)
                return value
            except ValueError:
                raise IllegalValueError("cycle point", keys, value)
        try:
            TimePointParser().parse(value)
        except ValueError:
            raise IllegalValueError('cycle point', keys, value)
        return value

    @classmethod
    def coerce_cycle_point_format(cls, value, keys):
        """Coerce to a cycle point format (either CCYYMM... or %Y%m...)."""
        value = cls.strip_and_unquote(keys, value)
        if not value:
            return None
        test_timepoint = TimePoint(year=2001, month_of_year=3, day_of_month=1,
                                   hour_of_day=4, minute_of_hour=30,
                                   second_of_minute=54)
        if '/' in value:
            raise IllegalValueError('cycle point format', keys, value)
        if '%' in value:
            try:
                TimePointDumper().strftime(test_timepoint, value)
            except ValueError:
                raise IllegalValueError('cycle point format', keys, value)
            return value
        if 'X' in value:
            for i in range(1, 101):
                dumper = TimePointDumper(num_expanded_year_digits=i)
                try:
                    dumper.dump(test_timepoint, value)
                except ValueError:
                    continue
                return value
            raise IllegalValueError('cycle point format', keys, value)
        dumper = TimePointDumper()
        try:
            dumper.dump(test_timepoint, value)
        except ValueError:
            raise IllegalValueError('cycle point format', keys, value)
        return value

    @classmethod
    def coerce_cycle_point_time_zone(cls, value, keys):
        """Coerce value to a cycle point time zone format - Z, +13, -0800..."""
        value = cls.strip_and_unquote(keys, value)
        if not value:
            return None
        test_timepoint = TimePoint(year=2001, month_of_year=3, day_of_month=1,
                                   hour_of_day=4, minute_of_hour=30,
                                   second_of_minute=54)
        dumper = TimePointDumper()
        test_timepoint_string = dumper.dump(test_timepoint, 'CCYYMMDDThhmmss')
        test_timepoint_string += value
        parser = TimePointParser(allow_only_basic=True)
        try:
            parser.parse(test_timepoint_string)
        except ValueError:
            raise IllegalValueError(
                'cycle point time zone format', keys, value)
        return value

    def coerce_interval(self, value, keys):
        """Coerce an ISO 8601 interval (or number: back-comp) into seconds."""
        value = self.strip_and_unquote(keys, value)
        if not value:
            # Allow explicit empty values.
            return None
        try:
            interval = DurationParser().parse(value)
        except ValueError:
            raise IllegalValueError("ISO 8601 interval", keys, value)
        days, seconds = interval.get_days_and_seconds()
        return DurationFloat(
            days * Calendar.default().SECONDS_IN_DAY + seconds)

    def coerce_interval_list(self, value, keys):
        """Coerce a list of intervals (or numbers: back-comp) into seconds."""
        return self.expand_list(
            self.strip_and_unquote_list(keys, value),
            keys,
            lambda v: self.coerce_interval(v, keys))

    @classmethod
    def coerce_parameter_list(cls, value, keys):
        """Coerce parameter list.

        Args:
            value (str):
                This can be a list of str values. Each str value must conform
                to the same restriction as a task name.
                Otherwise, this can be a mixture of int ranges and int values.
            keys (list):
                Keys in nested dict that represents the raw configuration.

        Return (list):
            A list of strings or a list of sorted integers.

        Raise:
            IllegalValueError:
                If value has both str and int range or if a str value breaks
                the task name restriction.
        """
        items = []
        can_only_be = None   # A flag to prevent mixing str and int range
        for item in cls.strip_and_unquote_list(keys, value):
            values = cls.parse_int_range(item)
            if values is not None:
                if can_only_be == str:
                    raise IllegalValueError(
                        'parameter', keys, value, 'mixing int range and str')
                can_only_be = int
                items.extend(values)
            elif cls._REC_NAME_SUFFIX.match(item):
                try:
                    int(item)
                except ValueError:
                    if can_only_be == int:
                        raise IllegalValueError(
                            'parameter', keys, value,
                            'mixing int range and str')
                    can_only_be = str
                items.append(item)
            else:
                raise IllegalValueError(
                    'parameter', keys, value, '%s: bad value' % item)
        try:
            return [int(item) for item in items]
        except ValueError:
            return items

    def coerce_xtrigger(self, value, keys):
        """Coerce a string into an xtrigger function context object.

        func_name(*func_args, **func_kwargs)
        Checks for legal string templates in arg values too.

        """

        label = keys[-1]
        value = self.strip_and_unquote(keys, value)
        if not value:
            raise IllegalValueError("xtrigger", keys, value)
        fname = None
        args = []
        kwargs = {}
        match = self._REC_TRIG_FUNC.match(value)
        if match is None:
            raise IllegalValueError("xtrigger", keys, value)
        fname, fargs, intvl = match.groups()
        if intvl:
            intvl = self.coerce_interval(intvl, keys)

        if fargs:
            # Extract function args and kwargs.
            for farg in fargs.split(r','):
                try:
                    key, val = farg.strip().split(r'=', 1)
                except ValueError:
                    args.append(self._coerce_type(farg.strip()))
                else:
                    kwargs[key.strip()] = self._coerce_type(val.strip())

        return SubFuncContext(label, fname, args, kwargs, intvl)

    @classmethod
    def _coerce_type(cls, value):
        """Convert value to int, float, or bool, if possible."""
        try:
            val = int(value)
        except ValueError:
            try:
                val = float(value)
            except ValueError:
                if value == 'False':
                    val = False
                elif value == 'True':
                    val = True
                else:
                    # Leave as string.
                    val = cls.strip_and_unquote([], value)
        return val


def cylc_config_validate(cfg_root, spec_root):
    """Short for "CylcConfigValidator().validate(...)"."""
    return CylcConfigValidator().validate(cfg_root, spec_root)

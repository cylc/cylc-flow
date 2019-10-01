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
"""Validate a nested dict parsed from a config file against a spec file.

Check all items are legal.
Check all values are legal (type; min, max, allowed options).
Coerce value type from string (to int, float, list, etc.).
Coerce more value type from string (to time point, duration, xtriggers, etc.).
Also provides default values from the spec as a nested dict.
"""

import re
import shlex
from collections import deque
from textwrap import dedent

from metomi.isodatetime.data import Duration, TimePoint, Calendar
from metomi.isodatetime.dumpers import TimePointDumper
from metomi.isodatetime.parsers import TimePointParser, DurationParser

from cylc.flow.parsec.exceptions import (
    ListValueError, IllegalValueError, IllegalItemError)
from cylc.flow.subprocctx import SubFuncContext


class ParsecValidator(object):
    """Type validator and coercer for configurations.

    Attributes:
        .coercers (dict):
            Map value type keys with coerce methods.
    """

    # quoted value regex reference:
    #   http://stackoverflow.com/questions/5452655/
    #   python-regex-to-match-text-in-single-quotes-
    #   ignoring-escaped-quotes-and-tabs-n

    # quoted list values not at end of line
    _REC_SQ_L_VALUE = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'")
    _REC_DQ_L_VALUE = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
    # quoted values with ignored trailing comments
    _REC_SQ_VALUE = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'(?:\s*(?:#.*)?)?$")
    _REC_DQ_VALUE = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"(?:\s*(?:#.*)?)?$')

    _REC_UQLP = re.compile(r"""(['"]?)(.*?)\1(,|$)""")
    _REC_SQV = re.compile(r"((?:^[^']*(?:'[^']*')*[^']*)*)(#.*)$")
    _REC_DQV = re.compile('((?:^[^"]*(?:"[^"]*")*[^"]*)*)(#.*)$')
    # quoted multi-line values
    _REC_MULTI_LINE_SINGLE = re.compile(
        r"\A'''(.*?)'''\s*(?:#.*)?\Z", re.MULTILINE | re.DOTALL)
    _REC_MULTI_LINE_DOUBLE = re.compile(
        r'\A"""(.*?)"""\s*(?:#.*)?\Z', re.MULTILINE | re.DOTALL)
    # integer range syntax START..END[..STEP]
    _REC_INT_RANGE = re.compile(
        r'\A([+\-]?\d+)\s*\.\.\s*([+\-]?\d+)(?:\s*\.\.\s*(\d+))?\Z')
    # Parameterized names containing at least one comma.
    _REC_MULTI_PARAM = re.compile(r'<[\w]+,.*?>')

    SELF_REFERENCE_PATTERNS = ['localhost', '127.0.0.1', '0.0.0.0']

    # Value type constants
    V_BOOLEAN = 'V_BOOLEAN'
    V_FLOAT = 'V_FLOAT'
    V_FLOAT_LIST = 'V_FLOAT_LIST'
    V_INTEGER = 'V_INTEGER'
    V_INTEGER_LIST = 'V_INTEGER_LIST'
    V_STRING = 'V_STRING'
    V_STRING_LIST = 'V_STRING_LIST'
    V_SPACELESS_STRING_LIST = 'V_SPACELESS_STRING_LIST'
    V_ABSOLUTE_HOST_LIST = 'V_ABSOLUTE_HOST_LIST'

    def __init__(self):
        self.coercers = {
            self.V_BOOLEAN: self.coerce_boolean,
            self.V_FLOAT: self.coerce_float,
            self.V_FLOAT_LIST: self.coerce_float_list,
            self.V_INTEGER: self.coerce_int,
            self.V_INTEGER_LIST: self.coerce_int_list,
            self.V_STRING: self.coerce_str,
            self.V_STRING_LIST: self.coerce_str_list,
            self.V_SPACELESS_STRING_LIST: self.coerce_spaceless_str_list,
            self.V_ABSOLUTE_HOST_LIST: self.coerce_absolute_host_list
        }

    def validate(self, cfg_root, spec_root):
        """Validate and coerce a nested dict against a parsec spec.

        Args:
            cfg_root (dict):
                A nested dict representing the raw configuration.
            spec_root (dict):
                A nested dict containing the spec for the configuration.

        Raises:
            IllegalItemError: on bad configuration items.
            IllegalValueError: on bad configuration values.
        """
        queue = deque([[cfg_root, spec_root, []]])
        while queue:
            # Walk items, breadth first
            cfg, spec, keys = queue.popleft()
            for key, value in cfg.items():
                if key not in spec:
                    if '__MANY__' not in spec:
                        raise IllegalItemError(keys, key)
                    else:
                        # only accept the item if its value is of the same type
                        # as that of the __MANY__  item, i.e. dict or not-dict.
                        val_is_dict = isinstance(value, dict)
                        spc_is_dict = isinstance(spec['__MANY__'], dict)
                        if (
                            keys != ['scheduling', 'graph'] and
                            not val_is_dict and
                            '  ' in key
                        ):
                            # Item names shouldn't have consecutive spaces
                            # (GitHub #2417)
                            raise IllegalItemError(
                                keys, key, 'consecutive spaces')
                        if ((val_is_dict and spc_is_dict) or
                                (not val_is_dict and not spc_is_dict)):
                            speckey = '__MANY__'
                        else:
                            raise IllegalItemError(keys, key)
                else:
                    speckey = key
                specval = spec[speckey]
                if isinstance(value, dict) and isinstance(specval, dict):
                    # Item is dict, push to queue
                    queue.append([value, specval, keys + [key]])
                elif value is not None and not isinstance(specval, dict):
                    # Item is value, coerce according to value type
                    cfg[key] = self.coercers[specval[0]](value, keys + [key])
                    # [vtype, option_default, option_2, option_3, ...]
                    if len(specval) > 2:
                        voptions = specval[1:]
                        if (isinstance(cfg[key], list) and
                                any(val not in voptions for val in cfg[key]) or
                                not isinstance(cfg[key], list) and
                                cfg[key] not in voptions):
                            raise IllegalValueError(
                                'option', keys + [key], cfg[key])

    __call__ = validate

    @classmethod
    def coerce_boolean(cls, value, keys):
        """Coerce value to a boolean."""
        value = cls.strip_and_unquote(keys, value)
        if value in ['True', 'true']:
            return True
        elif value in ['False', 'false']:
            return False
        elif value in ['', None]:
            return None
        else:
            raise IllegalValueError('boolean', keys, value)

    @classmethod
    def coerce_float(cls, value, keys):
        """Coerce value to a float."""
        value = cls.strip_and_unquote(keys, value)
        if value in ['', None]:
            return None
        try:
            return float(value)
        except ValueError:
            raise IllegalValueError('float', keys, value)

    @classmethod
    def coerce_float_list(cls, value, keys):
        """Coerce list values with optional multipliers to float."""
        values = cls.strip_and_unquote_list(keys, value)
        return cls.expand_list(values, keys, float)

    @classmethod
    def coerce_int(cls, value, keys):
        """Coerce value to an integer."""
        value = cls.strip_and_unquote(keys, value)
        if value in ['', None]:
            return None
        try:
            return int(value)
        except ValueError:
            raise IllegalValueError('int', keys, value)

    @classmethod
    def coerce_int_list(cls, value, keys):
        """Coerce list values with optional multipliers to integer."""
        items = []
        for item in cls.strip_and_unquote_list(keys, value):
            values = cls.parse_int_range(item)
            if values is None:
                items.extend(cls.expand_list([item], keys, int))
            else:
                items.extend(values)
        return items

    @classmethod
    def coerce_str(cls, value, keys):
        """Coerce value to a string."""
        if isinstance(value, list):
            # handle graph string merging
            vraw = []
            vals = [value]
            while vals:
                val = vals.pop()
                if isinstance(val, list):
                    vals.extend(reversed(val))  # reverse to preserve order
                else:
                    vraw.append(cls.strip_and_unquote(keys, val))
            value = '\n'.join(vraw)
        else:
            value = cls.strip_and_unquote(keys, value)
        return value

    @classmethod
    def coerce_str_list(cls, value, keys):
        """Coerce value to a list of strings."""
        return cls.strip_and_unquote_list(keys, value)

    @classmethod
    def coerce_spaceless_str_list(cls, value, keys):
        """Coerce value to a list of strings ensuring no values contain spaces.

        Examples:
            >>> ParsecValidator.coerce_spaceless_str_list(
            ...     'a, b c, d', ['foo'])  # doctest: +NORMALIZE_WHITESPACE
            Traceback (most recent call last):
            cylc.flow.parsec.exceptions.ListValueError: \
            (type=list) foo = a, b c, d - \
            (list item "b c" cannot contain a space character)

        """
        lst = cls.strip_and_unquote_list(keys, value)
        for item in lst:
            if ' ' in item:
                raise ListValueError(
                    keys, value,
                    msg='list item "%s" cannot contain a space character' %
                    item)
        return lst

    @classmethod
    def coerce_absolute_host_list(cls, value, keys):
        """Do not permit self reference in host names.

        Example:
            >>> ParsecValidator.coerce_absolute_host_list(
            ...     'foo, bar, 127.0.0.1:8080, baz', ['pub']
            ... )  # doctest: +NORMALIZE_WHITESPACE
            Traceback (most recent call last):
            cylc.flow.parsec.exceptions.ListValueError: \
                (type=list) pub = foo, bar, 127.0.0.1:8080, baz - \
                (ambiguous host "127.0.0.1:8080")

        """
        hosts = cls.coerce_spaceless_str_list(value, keys)
        for host in hosts:
            if any(host.startswith(pattern)
                   for pattern in cls.SELF_REFERENCE_PATTERNS):
                raise ListValueError(
                    keys, value, msg='ambiguous host "%s"' % host)
        return hosts

    @classmethod
    def expand_list(cls, values, keys, type_):
        """Handle multiplier syntax N*VALUE in a list."""
        lvalues = []
        for item in values:
            try:
                mult, val = item.split('*', 1)
            except ValueError:
                # too few values to unpack: no multiplier
                try:
                    lvalues.append(type_(item))
                except ValueError as exc:
                    raise IllegalValueError('list', keys, item, exc=exc)
            else:
                # mult * val
                try:
                    lvalues += int(mult) * [type_(val)]
                except ValueError as exc:
                    raise IllegalValueError('list', keys, item, exc=exc)
        return lvalues

    @classmethod
    def parse_int_range(cls, value):
        """Parse a value containing an integer range START..END[..STEP].

        Return (list):
            A list containing the integer values in range,
            or None if value does not contain an integer range.
        """
        match = cls._REC_INT_RANGE.match(value)
        if match:
            lower, upper, step = match.groups()
            if not step:
                step = 1
            return list(range(int(lower), int(upper) + 1, int(step)))
        else:
            return None

    @classmethod
    def strip_and_unquote(cls, keys, value):
        """Remove leading and trailing spaces and unquote value.

        Args:
            keys (list):
                Keys in nested dict that represents the raw configuration.
            value (str):
                String value in raw configuration.

        Return (str):
            Processed value.
        """
        for substr, rec in [
                ["'''", cls._REC_MULTI_LINE_SINGLE],
                ['"""', cls._REC_MULTI_LINE_DOUBLE],
                ['"', cls._REC_DQ_VALUE],
                ["'", cls._REC_SQ_VALUE]]:
            if value.startswith(substr):
                match = rec.match(value)
                if match:
                    value = match.groups()[0]
                else:
                    raise IllegalValueError("string", keys, value)
                break
        else:
            # unquoted
            value = value.split(r'#', 1)[0]

        # Note strip() removes leading and trailing whitespace, including
        # initial newlines on a multiline string:
        return dedent(value).strip()

    @classmethod
    def strip_and_unquote_list(cls, keys, value):
        """Remove leading and trailing spaces and unquote list value.

        Args:
            keys (list):
                Keys in nested dict that represents the raw configuration.
            value (str):
                String value in raw configuration that is supposed to be a
                comma separated list.

        Return (list):
            Processed value as a list.
        """
        if value.startswith('"') or value.startswith("'"):
            lexer = shlex.shlex(value, posix=True, punctuation_chars=",")
            lexer.commenters = '#'
            lexer.whitespace_split = False
            lexer.whitespace = "\t\n\r"
            lexer.wordchars += " "
            values = [t.strip() for t in lexer if t != "," and t.strip()]
        else:
            # unquoted values (may contain internal quoted strings with list
            # delimiters inside 'em!)
            for quotation, rec in (('"', cls._REC_DQV), ("'", cls._REC_SQV)):
                if quotation in value:
                    match = rec.match(value)
                    if match:
                        value = match.groups()[0]
                        break
            else:
                value = value.split(r'#', 1)[0].strip()
            values = list(cls._unquoted_list_parse(keys, value))
            # allow trailing commas
            if values[-1] == '':
                values = values[0:-1]
        return values

    @classmethod
    def _unquoted_list_parse(cls, keys, value):
        """Split comma separated list, and unquote each value."""
        # http://stackoverflow.com/questions/4982531/
        # how-do-i-split-a-comma-delimited-string-in-python-except-
        # for-the-commas-that-are

        # First detect multi-parameter lists like <m,n>.
        if cls._REC_MULTI_PARAM.search(value):
            raise ListValueError(
                keys, value,
                msg="names containing commas must be quoted"
                "(e.g. 'foo<m,n>')")
        pos = 0
        while True:
            match = cls._REC_UQLP.search(value, pos)
            result = match.group(2).strip()
            separator = match.group(3)
            yield result
            if not separator:
                break
            pos = match.end(0)


def parsec_validate(cfg_root, spec_root):
    """Short for "ParsecValidator().validate(...)"."""
    return ParsecValidator().validate(cfg_root, spec_root)


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

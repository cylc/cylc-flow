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
from typing import List, Dict, Any, Optional, Tuple

from metomi.isodatetime.data import Duration, TimePoint
from metomi.isodatetime.dumpers import TimePointDumper
from metomi.isodatetime.parsers import TimePointParser, DurationParser
from metomi.isodatetime.exceptions import IsodatetimeError, ISO8601SyntaxError

from cylc.flow.parsec.exceptions import (
    ListValueError, IllegalValueError, IllegalItemError)
from cylc.flow.subprocctx import SubFuncContext


class ParsecValidator:
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

    SELF_REFERENCE_PATTERNS = ['localhost', '127.0.0.1', '0.0.0.0']  # nosec
    # * these strings are used for validation purposes
    # * they are not used for binding

    # Value type constants
    V_BOOLEAN = 'V_BOOLEAN'
    V_FLOAT = 'V_FLOAT'
    V_FLOAT_LIST = 'V_FLOAT_LIST'
    V_INTEGER = 'V_INTEGER'
    V_INTEGER_LIST = 'V_INTEGER_LIST'
    V_RANGE = 'V_RANGE'
    V_STRING = 'V_STRING'
    V_STRING_LIST = 'V_STRING_LIST'
    V_SPACELESS_STRING_LIST = 'V_SPACELESS_STRING_LIST'
    V_ABSOLUTE_HOST_LIST = 'V_ABSOLUTE_HOST_LIST'

    V_TYPE_HELP = {
        # V_TYPE: (quick_name, help_string, examples_list, see_also)
        V_BOOLEAN: (
            'boolean',
            'A boolean in Python format',
            ['True', 'False']
        ),
        V_FLOAT: (
            'float',
            'A number in integer, decimal or exponential format',
            ['1', '1.1', '1.1e11']
        ),
        V_FLOAT_LIST: (
            'float list',
            'A comma separated list of floats.',
            ['1, 1.1, 1.1e11']
        ),
        V_INTEGER: (
            'integer',
            'An integer.',
            ['1', '2', '3']
        ),
        V_INTEGER_LIST: (
            'integer list',
            'A comma separated list of integers.',
            ['1, 2, 3', '1..3', '1..3, 7']
        ),
        V_RANGE: (
            'integer range',
            'An integer range specified by a minimum and maximum value.',
            {
                '1..5': 'The numbers 1 to 5 inclusive.',
            }
        ),
        V_STRING: (
            'string',
            'Plain text.',
            ['Hello World!']
        ),
        V_STRING_LIST: (
            'list',
            'A comma separated list of strings.',
            ['a, b c, d']
        ),
        V_SPACELESS_STRING_LIST: (
            'spaceless list',
            'A comma separated list of strings which cannot contain spaces.',
            ['a, b, c']
        ),
        V_ABSOLUTE_HOST_LIST: (
            'absolute host list',
            'A comma separated list of hostnames which does not contain '
            'any self references '
            f'(i.e. does not contain {", ".join(SELF_REFERENCE_PATTERNS)})',
            ['foo', 'bar', 'baz']
        )
    }

    def __init__(self):
        self.coercers = {
            self.V_BOOLEAN: self.coerce_boolean,
            self.V_FLOAT: self.coerce_float,
            self.V_FLOAT_LIST: self.coerce_float_list,
            self.V_INTEGER: self.coerce_int,
            self.V_INTEGER_LIST: self.coerce_int_list,
            self.V_RANGE: self.coerce_range,
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
                        spc_is_dict = not spec['__MANY__'].is_leaf()
                        if (
                            keys != ['scheduling', 'graph'] and
                            not val_is_dict and
                            '  ' in key
                        ):
                            # Item names shouldn't have consecutive spaces
                            # (GitHub #2417)
                            raise IllegalItemError(
                                keys, key, 'consecutive spaces')
                        if not (
                            (val_is_dict and spc_is_dict)
                            or (not val_is_dict and not spc_is_dict)
                        ):
                            raise IllegalItemError(keys, key)
                        speckey = '__MANY__'

                else:
                    speckey = key
                specval = spec[speckey]

                cfg_is_section = isinstance(value, dict)
                spec_is_section = not specval.is_leaf()
                if cfg_is_section and not spec_is_section:
                    # config is a [section] but it should be a setting=
                    raise IllegalItemError(
                        keys,
                        key,
                        msg=f'"{key}" should be a setting not a [section]',
                    )
                if (not cfg_is_section) and spec_is_section:
                    # config is a setting= but it should be a [section]
                    raise IllegalItemError(
                        keys,
                        key,
                        msg=f'"{key}" should be a [section] not a setting',
                    )

                if cfg_is_section and spec_is_section:
                    # Item is dict, push to queue
                    queue.append([value, specval, keys + [key]])
                elif value is not None and not spec_is_section:
                    # Item is value, coerce according to value type
                    cfg[key] = self.coercers[specval.vdr](value, keys + [key])
                    if specval.options:
                        voptions = specval.options
                        if (isinstance(cfg[key], list) and
                                any(val not in voptions for val in cfg[key]) or
                                not isinstance(cfg[key], list) and
                                cfg[key] not in voptions):
                            raise IllegalValueError(
                                'option', keys + [key], cfg[key])

    __call__ = validate

    @classmethod
    def coerce_boolean(cls, value, keys):
        """Coerce value to a boolean.

        Examples:
            >>> ParsecValidator.coerce_boolean('True', None)
            True
            >>> ParsecValidator.coerce_boolean('true', None)
            True

        """
        value = cls.strip_and_unquote(keys, value)
        if value in ['True', 'true']:
            return True
        elif value in ['False', 'false']:
            return False
        elif value in ['', None]:  # noqa: SIM106
            return None
        else:
            raise IllegalValueError('boolean', keys, value)

    @classmethod
    def coerce_float(cls, value, keys):
        """Coerce value to a float.

        Examples:
            >>> ParsecValidator.coerce_float('1', None)
            1.0
            >>> ParsecValidator.coerce_float('1.1', None)
            1.1
            >>> ParsecValidator.coerce_float('1.1e1', None)
            11.0

        """
        value = cls.strip_and_unquote(keys, value)
        if value in ['', None]:
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise IllegalValueError('float', keys, value, exc=exc) from None

    @classmethod
    def coerce_float_list(cls, value, keys):
        """Coerce list values with optional multipliers to float.

        Examples:
            >>> ParsecValidator.coerce_float_list('1, 1.1, 1.1e1', None)
            [1.0, 1.1, 11.0]

        """
        values = cls.strip_and_unquote_list(keys, value)
        return cls.expand_list(values, keys, float)

    @classmethod
    def coerce_int(cls, value, keys):
        """Coerce value to an integer.

        Examples:
            >>> ParsecValidator.coerce_int('1', None)
            1

        """
        value = cls.strip_and_unquote(keys, value)
        if value in ['', None]:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise IllegalValueError('int', keys, value, exc=exc) from None

    @classmethod
    def coerce_int_list(cls, value, keys):
        """Coerce list values with optional multipliers to integer.

        Examples:
            >>> ParsecValidator.coerce_int_list('1, 2, 3', None)
            [1, 2, 3]
            >>> ParsecValidator.coerce_int_list('1..3', None)
            [1, 2, 3]

        """
        items = []
        for item in cls.strip_and_unquote_list(keys, value):
            values = cls.parse_int_range(item)
            if values is None:
                items.extend(cls.expand_list([item], keys, int))
            else:
                items.extend(values)
        return items

    @classmethod
    def coerce_range(cls, value, keys):
        """A single min/max pair defining an integer range.

        Examples:
            >>> ParsecValidator.coerce_range('1..3', None)
            (1, 3)
            >>> ParsecValidator.coerce_range('1..3, 5', 'k')
            Traceback (most recent call last):
            cylc.flow.parsec.exceptions.ListValueError:
            (type=list) k = 1..3, 5 - (Only one min..max pair is permitted)
            >>> ParsecValidator.coerce_range('1..z', 'k')
            Traceback (most recent call last):
            cylc.flow.parsec.exceptions.ListValueError:
            (type=list) k = 1..z - (Integer range must be in the
            format min..max)
            >>> ParsecValidator.coerce_range('1', 'k')
            Traceback (most recent call last):
            cylc.flow.parsec.exceptions.ListValueError:
            (type=list) k = 1 - (Integer range must be in the
            format min..max)

        """
        items = cls.strip_and_unquote_list(keys, value)
        if len(items) != 1:
            raise ListValueError(
                keys,
                value,
                msg='Only one min..max pair is permitted',
            )
        item = items[0]
        match = cls._REC_INT_RANGE.match(item)
        if not match:
            raise ListValueError(
                keys,
                value,
                msg='Integer range must be in the format min..max',
            )
        min_, max_ = match.groups()[0:2]
        return Range((int(min_), int(max_)))

    @classmethod
    def coerce_str(cls, value, keys) -> str:
        """Coerce value to a string.

        Examples:
            >>> ParsecValidator.coerce_str('abc', None)
            'abc'
            >>> ParsecValidator.coerce_str(['abc', 'def'], None)
            'abc\\ndef'

        """
        if isinstance(value, list):
            # handle graph string merging
            vraw: List[str] = []
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
        """Coerce value to a list of strings.

        >>> ParsecValidator.coerce_str_list('a, b, c', None)
        ['a', 'b', 'c']
        >>> ParsecValidator.coerce_str_list('a, b c ,   d', None)
        ['a', 'b c', 'd']

        """
        return cls.strip_and_unquote_list(keys, value)

    @classmethod
    def coerce_spaceless_str_list(cls, value, keys):
        """Coerce value to a list of strings ensuring no values contain spaces.

        Examples:
            >>> ParsecValidator.coerce_spaceless_str_list(
            ...     'a, b, c', None)
            ['a', 'b', 'c']

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

        Examples:
            >>> ParsecValidator.coerce_absolute_host_list(
            ...     'foo, bar, baz', None)
            ['foo', 'bar', 'baz']

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
        """Handle multiplier syntax N*VALUE in a list.

        Examples:
            >>> ParsecValidator.expand_list(['1', '2*3'], None, int)
            [1, 3, 3]

        """
        lvalues = []
        for item in values:
            try:
                mult, val = item.split('*', 1)
            except ValueError:
                # too few values to unpack: no multiplier
                try:
                    lvalues.append(type_(item))
                except ValueError as exc:
                    raise IllegalValueError(
                        'list', keys, item, exc=exc
                    ) from None
            else:
                # mult * val
                try:
                    lvalues += int(mult) * [type_(val)]
                except ValueError as exc:
                    raise IllegalValueError(
                        'list', keys, item, exc=exc
                    ) from None
        return lvalues

    @classmethod
    def parse_int_range(cls, value):
        """Parse a value containing an integer range START..END[..STEP].

        Return (list):
            A list containing the integer values in range,
            or None if value does not contain an integer range.

        Examples:
            >>> ParsecValidator.parse_int_range('1..3')
            [1, 2, 3]

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
    def _unquote(cls, keys: List[str], value: str) -> Optional[str]:
        """Unquote value."""
        for substr, rec in (
            ("'''", cls._REC_MULTI_LINE_SINGLE),
            ('"""', cls._REC_MULTI_LINE_DOUBLE),
            ('"', cls._REC_DQ_VALUE),
            ("'", cls._REC_SQ_VALUE)
        ):
            if value.startswith(substr):
                match = rec.match(value)
                if not match:
                    raise IllegalValueError("string", keys, value)
                return match[1]
        return None

    @classmethod
    def strip_and_unquote(cls, keys: List[str], value: str) -> str:
        """Remove leading and trailing spaces and unquote value.

        Args:
            keys:
                Keys in nested dict that represents the raw configuration.
            value:
                String value in raw configuration.

        Return:
            Processed value.

        Examples:
            >>> ParsecValidator.strip_and_unquote(None, '" foo "')
            'foo'

        """
        val = cls._unquote(keys, value)
        if val is None:
            val = value.split(r'#', 1)[0]

        # Note strip() removes leading and trailing whitespace, including
        # initial newlines on a multiline string:
        return dedent(val).strip()

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

        Examples:
            >>> ParsecValidator.strip_and_unquote_list(None, ' 1 , "2", 3')
            ['1', '"2"', '3']

            >>> ParsecValidator.strip_and_unquote_list(None, '" 1 , 2", 3')
            ['1 , 2', '3']

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
        """Split comma separated list, and unquote each value.

        Examples:
            >>> list(ParsecValidator._unquoted_list_parse(None, '"1", 2'))
            ['1', '2']

        """
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


class Range(tuple):

    def __str__(self):
        return f'{self[0]} .. {self[1]}'


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
    V_CYCLE_POINT_WITH_OFFSETS = 'V_CYCLE_POINT_WITH_OFFSETS'
    V_INTERVAL = 'V_INTERVAL'
    V_INTERVAL_LIST = 'V_INTERVAL_LIST'
    V_PARAMETER_LIST = 'V_PARAMETER_LIST'
    V_XTRIGGER = 'V_XTRIGGER'

    V_TYPE_HELP: dict = {
        # V_TYPE: (quick_name, help_string, examples_list, see_also)
        V_CYCLE_POINT: (
            'cycle point',
            'An integer or date-time cycle point as appropriate.',
            {
                '1': 'An integer cycle point.',
                '2000-01-01T00:00Z': 'A date-time cycle point.',
                'now': 'The current date-time.',
                'next(T-00)':
                    'The current date-time rounded up to the nearest'
                    ' whole hour.'
            },
            [
                ('std:term', 'cycle point'),
                ('std:term', 'ISO8601 duration')
            ]
        ),
        V_CYCLE_POINT_FORMAT: (
            'cycle point format',
            'An time format for date-time cycle points in ``isodatetime`` '
            '"print" or "parse" format. '
            'See ``isodatetime --help`` for more information.',
            {
                'CCYYMM': '``isodatetime`` print format.',
                '%Y%m': '``isodatetime`` parse format.'
            }
        ),
        V_CYCLE_POINT_TIME_ZONE: (
            'cycle point time zone',
            'A time zone for date-time cycle points in ISO8601 format.',
            {
                'Z': 'UTC / GMT.',
                '+13': 'UTC plus 13 hours.',
                '-0830': 'UTC minus 8 hours and 30 minutes.'
            }
        ),
        V_CYCLE_POINT_WITH_OFFSETS: (
            'cycle point with support for offsets',
            'An integer or date-time cycle point, with optional offset(s).',
            {
                '1': 'An integer cycle point.',
                '1 +P5': (
                    'An integer cycle point with an offset'
                    ' (this evaluates as ``6``).'
                ),
                '+P5': (
                    'An integer cycle point offset.'
                    ' This offset is added to the initial cycle point'
                ),
                '2000-01-01T00:00Z': 'A date-time cycle point.',
                '2000-02-29T00:00Z +P1D +P1M': (
                    'A date-time cycle point with offsets'
                    ' (this evaluates as ``2000-04-01T00:00Z``).'
                ),
            }
        ),
        V_INTERVAL: (
            'time interval',
            'An ISO8601 duration.',
            {
                'P1Y': 'Every year.',
                'PT6H': 'Every six hours.'
            },
            [('std:term', 'ISO8601 duration')]
        ),
        V_INTERVAL_LIST: (
            'time interval list',
            'A comma separated list of time intervals. '
            'These can include multipliers.',
            {
                'P1Y, P2Y, P3Y': 'After 1, 2 and 3 years.',
                'PT1M, 2*PT1H, P1D': 'After 1 minute, 1 hour, 1 hour and 1 '
                'day'
            },
            [('std:term', 'ISO8601 duration')]
        ),
        V_PARAMETER_LIST: (
            'parameter list',
            'A comma separated list of Cylc parameter values. '
            'This can include strings, integers and integer ranges.',
            {
                'foo, bar, baz': 'List of string parameters.',
                '1, 2, 3': 'List of integer parameters.',
                '1..3': 'The same as 1, 2, 3.',
                '1..5..2': 'The same as 1, 3, 5.',
                '1..5..2, 8': 'Range and integers can be mixed.',
            },
            [('ref', 'User Guide Param')]
        ),
        V_XTRIGGER: (
            'xtrigger function signature',
            'A function signature similar to how it would be written in '
            'Python.\n'
            '``<function>(<arg>, <kwarg>=<value>):<interval>``',
            {
                'mytrigger(42, cycle_point=%(point)):PT10S':
                    'Run function ``mytrigger`` every 10 seconds.'
            },
            [('ref', 'Section External Triggers')]
        )
    }

    def __init__(self):
        ParsecValidator.__init__(self)
        self.coercers.update({
            self.V_CYCLE_POINT: self.coerce_cycle_point,
            self.V_CYCLE_POINT_FORMAT: self.coerce_cycle_point_format,
            self.V_CYCLE_POINT_TIME_ZONE: self.coerce_cycle_point_time_zone,
            # NOTE: This type exists for documentation reasons
            # it doesn't actually process offsets, that happens later
            self.V_CYCLE_POINT_WITH_OFFSETS: self.coerce_str,
            self.V_INTERVAL: self.coerce_interval,
            self.V_INTERVAL_LIST: self.coerce_interval_list,
            self.V_PARAMETER_LIST: self.coerce_parameter_list,
            self.V_XTRIGGER: self.coerce_xtrigger,
        })

    @classmethod
    def coerce_cycle_point(cls, value, keys):
        """Coerce value to a cycle point.

        Examples:
            >>> CylcConfigValidator.coerce_cycle_point('2000', None)
            '2000'
            >>> CylcConfigValidator.coerce_cycle_point('now', None)
            'now'
            >>> CylcConfigValidator.coerce_cycle_point('next(T-00)', None)
            'next(T-00)'

        """
        if not value:
            return None
        value = cls.strip_and_unquote(keys, value)
        if value == 'now':
            # Handle this later in config.py when workflow UTC mode is known.
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
                except IsodatetimeError:
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
            except IsodatetimeError as exc:
                raise IllegalValueError(
                    'cycle point', keys, value, exc=exc
                ) from None
        try:
            TimePointParser().parse(value)
        except IsodatetimeError as exc:
            if isinstance(exc, ISO8601SyntaxError):
                # Don't know cycling mode yet, so override ISO8601-specific msg
                details = {'msg': "Invalid cycle point"}
            else:
                details = {'exc': exc}
            raise IllegalValueError(
                'cycle point', keys, value, **details
            ) from None
        return value

    @classmethod
    def coerce_cycle_point_format(cls, value, keys):
        """Coerce to a cycle point format.

        Examples:
            >>> CylcConfigValidator.coerce_cycle_point_format(
            ...     'CCYYMM', None)
            'CCYYMM'
            >>> CylcConfigValidator.coerce_cycle_point_format(
            ...     '%Y%m', None)
            '%Y%m'

        """
        value = cls.strip_and_unquote(keys, value)
        if not value:
            return None
        test_timepoint = TimePoint(year=2001, month_of_year=3, day_of_month=1,
                                   hour_of_day=4, minute_of_hour=30,
                                   second_of_minute=54)
        if '/' in value:
            raise IllegalValueError(
                'cycle point format', keys, value, msg=(
                    'Illegal character: "/".'
                    ' Datetimes are used in Cylc file paths.'
                )
            )
        if ':' in value:
            raise IllegalValueError(
                'cycle point format', keys, value, msg=(
                    'Illegal character: ":".'
                    ' Datetimes are used in Cylc file paths.'
                )
            )
        if '%' in value:
            try:
                TimePointDumper().strftime(test_timepoint, value)
            except IsodatetimeError as exc:
                raise IllegalValueError(
                    'cycle point format', keys, value, exc=exc
                ) from None
            return value
        if 'X' in value:
            for i in range(1, 101):
                dumper = TimePointDumper(num_expanded_year_digits=i)
                try:
                    dumper.dump(test_timepoint, value)
                except IsodatetimeError:
                    continue
                return value
            raise IllegalValueError('cycle point format', keys, value)
        dumper = TimePointDumper()
        try:
            dumper.dump(test_timepoint, value)
        except IsodatetimeError as exc:
            raise IllegalValueError(
                'cycle point format', keys, value, exc=exc
            ) from None
        return value

    @classmethod
    def coerce_cycle_point_time_zone(cls, value, keys):
        """Coerce value to a cycle point time zone format.

        Examples:
            >>> CylcConfigValidator.coerce_cycle_point_time_zone(
            ...     'Z', None)
            'Z'
            >>> CylcConfigValidator.coerce_cycle_point_time_zone(
            ...     '+13', None)
            '+13'
            >>> CylcConfigValidator.coerce_cycle_point_time_zone(
            ...     '-0800', None)
            '-0800'

        """
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
        except ValueError as exc:  # not IsodatetimeError as too specific
            raise IllegalValueError(
                'cycle point time zone format', keys, value, exc=exc
            ) from None
        return value

    @classmethod
    def coerce_interval(cls, value, keys):
        """Coerce an ISO 8601 interval into seconds.

        Examples:
            >>> CylcConfigValidator.coerce_interval('PT1H', None)
            3600.0

        """
        value = cls.strip_and_unquote(keys, value)
        if not value:
            # Allow explicit empty values.
            return None
        try:
            interval = DurationParser().parse(value)
        except IsodatetimeError as exc:
            raise IllegalValueError(
                "ISO 8601 interval", keys, value, exc=exc
            ) from None
        return DurationFloat(interval.get_seconds())

    @classmethod
    def coerce_interval_list(cls, value, keys):
        """Coerce a list of intervals into seconds.

        Examples:
            >>> CylcConfigValidator.coerce_interval_list('PT1H, PT2H', None)
            [3600.0, 7200.0]

        """
        return cls.expand_list(
            cls.strip_and_unquote_list(keys, value),
            keys,
            lambda v: cls.coerce_interval(v, keys))

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

        Examples:
            >>> CylcConfigValidator.coerce_parameter_list('1..4, 6', None)
            [1, 2, 3, 4, 6]

            >>> CylcConfigValidator.coerce_parameter_list('a, b, c', None)
            ['a', 'b', 'c']

            >>> CylcConfigValidator.coerce_parameter_list('084_132', None)
            ['084_132']

            >>> CylcConfigValidator.coerce_parameter_list('072, a', None)
            ['072', 'a']
        """
        items = []
        can_only_be = None   # A flag to prevent mixing str and int range
        for item in cls.strip_and_unquote_list(keys, value):
            values = cls.parse_int_range(item)
            if values is not None:
                if can_only_be is str:
                    raise IllegalValueError(
                        'parameter', keys, value, 'mixing int range and str')
                can_only_be = int
                items.extend(values)
            elif cls._REC_NAME_SUFFIX.match(item):  # noqa: SIM106
                try:
                    if '_' in item:
                        # Disable PEP-515 int coercion; go to except block:
                        raise ValueError()
                    int(item)
                except ValueError:
                    if can_only_be is int:
                        raise IllegalValueError(
                            'parameter',
                            keys,
                            value,
                            'mixing int range and str',
                        ) from None
                    can_only_be = str
                items.append(item)
            else:
                raise IllegalValueError(
                    'parameter', keys, value, '%s: bad value' % item)

        if can_only_be is str:
            return items

        try:
            return [int(item) for item in items]
        except ValueError:
            return items

    @staticmethod
    def parse_xtrig_arglist(value: str) -> Tuple[List[Any], Dict[str, Any]]:
        """Parse Pythonic-like arg/kwarg signatures.

        A stateful parser treats all args/kwargs as strings with
        implicit quoting.

        Examples:
            >>> parse = CylcConfigValidator.parse_xtrig_arglist

            # Parse pythonic syntax
            >>> parse('a, b, c, d=1, e=2,')
            (['a', 'b', 'c'], {'d': '1', 'e': '2'})
            >>> parse('a, "1,2,3", b=",=",')
            (['a', '"1,2,3"'], {'b': '",="'})
            >>> parse('a, "b c", '"'d=e '")
            (['a', '"b c"', "'d=e '"], {})

            # Parse implicit (i.e. unquoted) strings
            >>> parse('%(cycle)s, %(task)s, output=succeeded')
            (['%(cycle)s', '%(task)s'], {'output': 'succeeded'})

        """
        # results
        args = []
        kwargs = {}
        # state
        in_str = False  # are we inside a quoted string
        in_kwarg = False  # are we after the = sign of a kwarg
        buffer = ''  # the current argument being parsed
        kwarg_buffer = ''  # the key of a kwarg if in_kwarg == True
        # parser
        for char in value:
            if char in {'"', "'"}:
                in_str = not in_str
                buffer += char
            elif not in_str and char == ',':
                if in_kwarg:
                    kwargs[kwarg_buffer.strip()] = buffer.strip()
                    in_kwarg = False
                    kwarg_buffer = ''
                else:
                    args.append(buffer.strip())
                buffer = ''
            elif char == '=' and not in_str and not in_kwarg:
                in_kwarg = True
                kwarg_buffer = buffer
                buffer = ''
            else:
                buffer += char

        # reached the end of the string
        if buffer:
            if in_kwarg:
                kwargs[kwarg_buffer.strip()] = buffer.strip()
            else:
                args.append(buffer.strip())

        return args, kwargs

    @classmethod
    def coerce_xtrigger(cls, value, keys):
        """Coerce a string into an xtrigger function context object.

        func_name(*func_args, **func_kwargs)
        Checks for legal string templates in arg values too.

        Examples:
            >>> xtrig = CylcConfigValidator.coerce_xtrigger

            >>> ctx = xtrig('a(b, c):PT1M', [None])
            >>> ctx.get_signature()
            'a(b, c)'
            >>> ctx.intvl
            60.0

            # cast types
            >>> x = xtrig('a(1, 1.1, True, abc, x=True, y=1.1)', [None])
            >>> x.func_args
            [1, 1.1, True, 'abc']
            >>> x.func_kwargs
            {'x': True, 'y': 1.1}

        """
        label = keys[-1]
        value = cls.strip_and_unquote(keys, value)
        if not value:
            raise IllegalValueError("xtrigger", keys, value)
        match = cls._REC_TRIG_FUNC.match(value)
        if match is None:
            raise IllegalValueError("xtrigger", keys, value)
        fname, fargs, intvl = match.groups()
        if intvl:
            intvl = cls.coerce_interval(intvl, keys)

        # parse args
        args, kwargs = CylcConfigValidator.parse_xtrig_arglist(fargs or '')

        # cast types
        args = [
            CylcConfigValidator._coerce_type(arg)
            for arg in args
        ]
        kwargs = {
            key: CylcConfigValidator._coerce_type(value)
            for key, value in kwargs.items()
        }

        return SubFuncContext(label, fname, args, kwargs, intvl)

    @classmethod
    def _coerce_type(cls, value):
        """Convert value to int, float, bool, or None, if possible.

        Examples:
            >>> CylcConfigValidator._coerce_type('1')
            1
            >>> CylcConfigValidator._coerce_type('1.1')
            1.1
            >>> CylcConfigValidator._coerce_type('True')
            True
            >>> CylcConfigValidator._coerce_type('abc')
            'abc'
            >>> CylcConfigValidator._coerce_type('None')

        """
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
                elif value == 'None':
                    val = None
                else:
                    # Leave as string.
                    val = cls.strip_and_unquote([], value)
        return val


class BroadcastConfigValidator(CylcConfigValidator):
    """Validate and Coerce DB loaded broadcast config to internal objects."""
    def __init__(self):
        CylcConfigValidator.__init__(self)

    @classmethod
    def coerce_str(cls, value, keys) -> str:
        """Coerce value to a string. Unquotes & strips lead/trail whitespace.

        Prevents ParsecValidator from assuming '#' means comments;
        '#' has valid uses in shell script such as parameter substitution.

        Examples:
            >>> BroadcastConfigValidator.coerce_str('echo "${FOO#*bar}"', None)
            'echo "${FOO#*bar}"'
        """
        val = ParsecValidator._unquote(keys, value) or value
        return dedent(val).strip()

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

        Examples:
            >>> BroadcastConfigValidator.strip_and_unquote_list(
            ...    None, '["1, 2", 3]'
            ... )
            ['1, 2', '3']
        """
        if value.startswith('[') and value.endswith(']'):
            value = value.lstrip('[').rstrip(']')
        return ParsecValidator.strip_and_unquote_list(keys, value)

    # BACK COMPAT: BroadcastConfigValidator.coerce_interval
    # The DB at 8.0.x stores Interval values as neither ISO8601 duration
    # string or DurationFloat. This has been fixed at 8.1.0, and
    # the following method acts as a bridge between fixed and broken.
    # url:
    #     https://github.com/cylc/cylc-flow/pull/5138
    # from:
    #    8.0.x
    # to:
    #    8.1.x
    # remove at:
    #    8.x
    @classmethod
    def coerce_interval(cls, value, keys):
        """Coerce an ISO 8601 interval into seconds.

        Examples:
            >>> BroadcastConfigValidator.coerce_interval('PT1H', None)
            3600.0
            >>> x = BroadcastConfigValidator.coerce_interval('62', None)
            >>> x
            62.0
            >>> str(x)
            'PT1M2S'

        """
        value = cls.strip_and_unquote(keys, value)
        if not value:
            # Allow explicit empty values.
            return None
        try:
            interval = DurationParser().parse(value)
        except IsodatetimeError:
            try:
                interval = DurationParser().parse(str(DurationFloat(value)))
            except IsodatetimeError as exc:
                raise IllegalValueError(
                    "ISO 8601 interval", keys, value, exc=exc
                ) from None
        return DurationFloat(interval.get_seconds())


def cylc_config_validate(cfg_root, spec_root):
    """Short for "CylcConfigValidator().validate(...)"."""
    return CylcConfigValidator().validate(cfg_root, spec_root)

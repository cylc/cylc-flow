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
"""Validate a nested dict parsed from a config file against a spec file.

Check all items are legal.
Check all values are legal (type; min, max, allowed options).
Coerce value type from string (to int, float, list, etc.).
Also provides default values from the spec as a nested dict.
"""

from collections import deque
import json
from pipes import quote
import re
from textwrap import dedent

from isodatetime.data import Calendar, Duration, TimePoint
from isodatetime.dumpers import TimePointDumper
from isodatetime.parsers import DurationParser, TimePointParser
from wallclock import get_current_time_string

from parsec import ParsecError
from parsec.util import itemstr


class DurationFloat(float):
    """Duration in floating point seconds, but stringify as ISO8601 format."""

    def __str__(self):
        return str(Duration(seconds=self, standardize=True))


class SubProcContext(object):
    """Represent the context of an external command to run as a subprocess.

    Attributes:
        .cmd (list/str):
            The command to run expressed as a list (or as a str if shell=True
            is set in cmd_kwargs).
        .cmd_key (str):
            A key to identify the type of command. E.g. "jobs-submit".
        .cmd_kwargs (dict):
            Extra information about the command. This may contain:
                env (dict):
                    Specify extra environment variables for command.
                err (str):
                    Default STDERR content.
                out (str):
                    Default STDOUT content.
                ret_code (int):
                    Default return code.
                shell (boolean):
                    Launch command with "/bin/sh"?
                stdin_file_paths (list):
                    Files with content to send to command's STDIN.
                stdin_str (str):
                    Content to send to command's STDIN.
        .err (str):
            Content of the command's STDERR.
        .out (str)
            Content of the command's STDOUT.
        .ret_code (int):
            Return code of the command.
        .timestamp (str):
            Time string of latest update.
        .proc_pool_timeout (float):
            command execution timeout.
    """

    # Format string for single line output
    JOB_LOG_FMT_1 = '[%(cmd_key)s %(attr)s] %(mesg)s'
    # Format string for multi-line output
    JOB_LOG_FMT_M = '[%(cmd_key)s %(attr)s]\n%(mesg)s'

    def __init__(self, cmd_key, cmd, **cmd_kwargs):
        self.timestamp = get_current_time_string()
        self.cmd_key = cmd_key
        self.cmd = cmd
        self.cmd_kwargs = cmd_kwargs

        self.err = cmd_kwargs.get('err')
        self.ret_code = cmd_kwargs.get('ret_code')
        self.out = cmd_kwargs.get('out')

    def __str__(self):
        ret = ''
        for attr in 'cmd', 'ret_code', 'out', 'err':
            value = getattr(self, attr, None)
            if value is not None and str(value).strip():
                mesg = ''
                if attr == 'cmd' and self.cmd_kwargs.get('stdin_file_paths'):
                    mesg += 'cat'
                    for file_path in self.cmd_kwargs.get('stdin_file_paths'):
                        mesg += ' ' + quote(file_path)
                    mesg += ' | '
                if attr == 'cmd' and isinstance(value, list):
                    mesg += ' '.join(quote(item) for item in value)
                else:
                    mesg = str(value).strip()
                if attr == 'cmd' and self.cmd_kwargs.get('stdin_str'):
                    mesg += ' <<<%s' % quote(self.cmd_kwargs.get('stdin_str'))
                if len(mesg.splitlines()) > 1:
                    fmt = self.JOB_LOG_FMT_M
                else:
                    fmt = self.JOB_LOG_FMT_1
                if not mesg.endswith('\n'):
                    mesg += '\n'
                ret += fmt % {
                    'cmd_key': self.cmd_key,
                    'attr': attr,
                    'mesg': mesg}
        return ret.rstrip()


class SubFuncContext(SubProcContext):
    """Represent the context of a Python function to run as a subprocess.

    Attributes:
        # See also parent class attributes.
        .label (str):
            function label under [xtriggers] in suite.rc
        .func_name (str):
            function name
        .func_args (list):
            function positional args
        .func_kwargs (dict):
            function keyword args
        .intvl (float - seconds):
            function call interval (how often to check the external trigger)
        .ret_val (bool, dict)
            function return: (satisfied?, result to pass to trigger tasks)
    """

    DEFAULT_INTVL = 10.0

    def __init__(self, label, func_name, func_args, func_kwargs, intvl=None):
        """Initialize a function context."""
        self.label = label
        self.func_name = func_name
        self.func_kwargs = func_kwargs
        self.func_args = func_args
        try:
            self.intvl = float(intvl)
        except (TypeError, ValueError):
            self.intvl = self.DEFAULT_INTVL
        self.ret_val = (False, None)  # (satisfied, broadcast)
        super(SubFuncContext, self).__init__(
            'xtrigger-func', cmd=[], shell=False)

    def update_command(self, suite_source_dir):
        """Update the function wrap command after changes."""
        self.cmd = ['cylc-function-run', self.func_name,
                    json.dumps(self.func_args),
                    json.dumps(self.func_kwargs),
                    suite_source_dir]

    def get_signature(self):
        """Return the function call signature (as a string)."""
        skeys = sorted(self.func_kwargs.keys())
        args = self.func_args + [
            "%s=%s" % (i, self.func_kwargs[i]) for i in skeys]
        return "%s(%s)" % (self.func_name, ", ".join([str(a) for a in args]))


class ValidationError(ParsecError):
    """Base class for bad setting errors."""
    pass


class ListValueError(ValidationError):
    """Bad setting value, for a comma separated list."""
    def __init__(self, keys, value, exc=None):
        ValidationError.__init__(self)
        self.msg = (
            "ERROR: names containing commas must be quoted"
            " (e.g. 'foo<m,n>'):\n   %s" % itemstr(
                keys[:-1], keys[-1], value=value))
        if exc:
            self.msg += ": %s" % exc


class IllegalValueError(ValidationError):
    """Bad setting value."""
    def __init__(self, vtype, keys, value, exc=None):
        ValidationError.__init__(self)
        self.msg = 'Illegal %s value: %s' % (
            vtype, itemstr(keys[:-1], keys[-1], value=value))
        if exc:
            self.msg += ": %s" % exc


class IllegalItemError(ValidationError):
    """Bad setting section or option name."""
    def __init__(self, keys, key, msg=None):
        ValidationError.__init__(self)
        if msg is not None:
            self.msg = 'Illegal item (%s): %s' % (msg, itemstr(keys, key))
        else:
            self.msg = 'Illegal item: %s' % itemstr(keys, key)


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
    _REC_SQ_VALUE = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'(?:\s*(?:\#.*)?)?$")
    _REC_DQ_VALUE = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"(?:\s*(?:\#.*)?)?$')

    _REC_UQLP = re.compile(r"""(['"]?)(.*?)\1(,|$)""")
    _REC_SQV = re.compile(r"((?:^[^']*(?:'[^']*')*[^']*)*)(#.*)$")
    _REC_DQV = re.compile('((?:^[^"]*(?:"[^"]*")*[^"]*)*)(#.*)$')
    # quoted multi-line values
    _REC_MULTI_LINE_SINGLE = re.compile(
        r"\A'''(.*?)'''\s*(?:#.*)?\Z", re.MULTILINE | re.DOTALL)
    _REC_MULTI_LINE_DOUBLE = re.compile(
        r'\A"""(.*?)"""\s*(?:#.*)?\Z', re.MULTILINE | re.DOTALL)
    # Paramterized names containing at least one comma.
    _REC_MULTI_PARAM = re.compile(r'<[\w]+,.*?>')
    _REC_PARAM_INT_RANGE = re.compile(
        r'\A([\+\-]?\d+)\.\.([\+\-]?\d+)(?:\.\.(\d+))?\Z')
    _REC_NAME_SUFFIX = re.compile(r'\A[\w\-+%@]+\Z')
    _REC_TRIG_FUNC = re.compile(r'(\w+)\((.*)\)(?:\:(\w+))?')

    # Value type constants
    V_BOOLEAN = 'V_BOOLEAN'
    V_CYCLE_POINT = 'V_CYCLE_POINT'
    V_CYCLE_POINT_FORMAT = 'V_CYCLE_POINT_FORMAT'
    V_CYCLE_POINT_TIME_ZONE = 'V_CYCLE_POINT_TIME_ZONE'
    V_FLOAT = 'V_FLOAT'
    V_FLOAT_LIST = 'V_FLOAT_LIST'
    V_INTEGER = 'V_INTEGER'
    V_INTEGER_LIST = 'V_INTEGER_LIST'
    V_INTERVAL = 'V_INTERVAL'
    V_INTERVAL_LIST = 'V_INTERVAL_LIST'
    V_PARAMETER_LIST = 'V_PARAMETER_LIST'
    V_STRING = 'V_STRING'
    V_STRING_LIST = 'V_STRING_LIST'
    V_XTRIGGER = 'V_XTRIGGER'

    def __init__(self):
        self.coercers = {
            self.V_BOOLEAN: self._coerce_boolean,
            self.V_CYCLE_POINT: self._coerce_cycle_point,
            self.V_CYCLE_POINT_FORMAT: self._coerce_cycle_point_format,
            self.V_CYCLE_POINT_TIME_ZONE: self._coerce_cycle_point_time_zone,
            self.V_FLOAT: self._coerce_float,
            self.V_FLOAT_LIST: self._coerce_float_list,
            self.V_INTEGER: self._coerce_int,
            self.V_INTEGER_LIST: self._coerce_int_list,
            self.V_INTERVAL: self._coerce_interval,
            self.V_INTERVAL_LIST: self._coerce_interval_list,
            self.V_PARAMETER_LIST: self._coerce_parameter_list,
            self.V_STRING: self._coerce_str,
            self.V_STRING_LIST: self._coerce_str_list,
            self.V_XTRIGGER: self._coerce_xtrigger,
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
                        if not val_is_dict and '  ' in key:
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

    @classmethod
    def _coerce_boolean(cls, value, keys):
        """Coerce value to a boolean."""
        value = cls._strip_and_unquote(keys, value)
        if value in ['True', 'true']:
            return True
        elif value in ['False', 'false']:
            return False
        elif value in ['', None]:
            return None
        else:
            raise IllegalValueError('boolean', keys, value)

    @classmethod
    def _coerce_cycle_point(cls, value, keys):
        """Coerce value to a cycle point."""
        if not value:
            return None
        value = cls._strip_and_unquote(keys, value)
        if value == 'now':
            # Handle this later in config.py when the suite UTC mode is known.
            return value
        if value.isdigit():
            # Could be an old date-time cycle point format, or integer format.
            return value
        if value.startswith('-') or value.startswith('+'):
            # We don't know the value given for num expanded year digits...
            for i in range(1, 101):
                try:
                    TimePointParser(num_expanded_year_digits=i).parse(value)
                except ValueError:
                    continue
                return value
            raise IllegalValueError('cycle point', keys, value)
        try:
            TimePointParser().parse(value)
        except ValueError:
            raise IllegalValueError('cycle point', keys, value)
        return value

    @classmethod
    def _coerce_cycle_point_format(cls, value, keys):
        """Coerce to a cycle point format (either CCYYMM... or %Y%m...)."""
        value = cls._strip_and_unquote(keys, value)
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
    def _coerce_cycle_point_time_zone(cls, value, keys):
        """Coerce value to a cycle point time zone format - Z, +13, -0800..."""
        value = cls._strip_and_unquote(keys, value)
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

    @classmethod
    def _coerce_float(cls, value, keys):
        """Coerce value to a float."""
        value = cls._strip_and_unquote(keys, value)
        if value in ['', None]:
            return None
        try:
            return float(value)
        except ValueError:
            raise IllegalValueError('float', keys, value)

    @classmethod
    def _coerce_float_list(cls, value, keys):
        "Coerce list values with optional multipliers to float."
        values = cls._strip_and_unquote_list(keys, value)
        return cls._expand_list(values, keys, float)

    @classmethod
    def _coerce_int(cls, value, keys):
        """Coerce value to an integer."""
        value = cls._strip_and_unquote(keys, value)
        if value in ['', None]:
            return None
        try:
            return int(value)
        except ValueError:
            raise IllegalValueError('int', keys, value)

    @classmethod
    def _coerce_int_list(cls, value, keys):
        "Coerce list values with optional multipliers to integer."
        values = cls._strip_and_unquote_list(keys, value)
        return cls._expand_list(values, keys, int)

    def _coerce_interval(self, value, keys):
        """Coerce an ISO 8601 interval (or number: back-comp) into seconds."""
        value = self._strip_and_unquote(keys, value)
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

    def _coerce_interval_list(self, value, keys):
        """Coerce a list of intervals (or numbers: back-comp) into seconds."""
        return self._expand_list(
            self._strip_and_unquote_list(keys, value),
            keys,
            lambda v: self._coerce_interval(v, keys))

    @classmethod
    def _coerce_parameter_list(cls, value, keys):
        """Coerce parameter list.

        Args:
            value (str):
                This can be a list of str values. Each str value must conform
                to the same restriction as a task name.
                Otherwise, this can be a mixture of int ranges and int values.

        Return (list):
            A list of strings or a list of sorted integers.

        Raise:
            IllegalValueError:
                If value has both str and int range or if a str value breaks
                the task name restriction.
        """
        items = []
        can_only_be = None   # A flag to prevent mixing str and int range
        for item in cls._strip_and_unquote_list(keys, value):
            match = cls._REC_PARAM_INT_RANGE.match(item)
            if match:
                if can_only_be == str:
                    raise IllegalValueError(
                        'parameter', keys, value, 'mixing int range and str')
                can_only_be = int
                lower, upper, step = match.groups()
                if not step:
                    step = 1
                items.extend(range(int(lower), int(upper) + 1, int(step)))
            elif cls._REC_NAME_SUFFIX.match(item):
                if not item.isdigit():
                    if can_only_be == int:
                        raise IllegalValueError(
                            'parameter', keys, value,
                            'mixing int range and str')
                    can_only_be = str
                items.append(item)
            else:
                raise IllegalValueError(
                    'parameter', keys, value, '%s: bad value' % item)
        if not items or can_only_be == str or any(
                not str(item).isdigit() for item in items):
            return items
        else:
            return [int(item) for item in items]

    @classmethod
    def _coerce_str(cls, value, keys):
        """Coerce value to a string."""
        if isinstance(value, list):
            # handle graph string merging
            vraw = []
            for val in value:
                vraw.append(cls._strip_and_unquote(keys, val))
            value = '\n'.join(vraw)
        else:
            value = cls._strip_and_unquote(keys, value)
        return value

    @classmethod
    def _coerce_str_list(cls, value, keys):
        """Coerce value to a list of strings."""
        return cls._strip_and_unquote_list(keys, value)

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
                    val = cls._strip_and_unquote([], value)
        return val

    def _coerce_xtrigger(self, value, keys):
        """Coerce a string into an xtrigger function context object.

        func_name(*func_args, **func_kwargs)
        Checks for legal string templates in arg values too.

        """

        label = keys[-1]
        value = self._strip_and_unquote(keys, value)
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
            intvl = self._coerce_interval(intvl, keys)

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
    def _expand_list(cls, values, keys, type_):
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
                    raise IllegalValueError('list', keys, item, exc)
            else:
                # mult * val
                try:
                    lvalues += int(mult) * [type_(val)]
                except ValueError as exc:
                    raise IllegalValueError('list', keys, item, exc)
        return lvalues

    @classmethod
    def _strip_and_unquote(cls, keys, value):
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
    def _strip_and_unquote_list(cls, keys, value):
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
        if value.startswith('"'):
            # double-quoted values
            match = cls._REC_DQV.match(value)
            if match:
                value = match.groups()[0]
            values = cls._REC_DQ_L_VALUE.findall(value)
        elif value.startswith("'"):
            # single-quoted values
            match = cls._REC_SQV.match(value)
            if match:
                value = match.groups()[0]
            values = cls._REC_SQ_L_VALUE.findall(value)
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
            raise ListValueError(keys, value)

        pos = 0
        while True:
            match = cls._REC_UQLP.search(value, pos)
            result = match.group(2).strip()
            separator = match.group(3)
            yield result
            if not separator:
                break
            pos = match.end(0)

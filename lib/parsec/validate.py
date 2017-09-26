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
"""Validate a nested dict parsed from a config file against a spec file.

Check all items are legal.
Check all values are legal (type; min, max, allowed options).
Coerce value type from string (to int, float, list, etc.).
Also provides default values from the spec as a nested dict.
"""

import re
import sys
from parsec import ParsecError
from parsec.OrderedDict import OrderedDictWithDefaults
from parsec.util import m_override, un_many, itemstr


# quoted value regex reference:
#   http://stackoverflow.com/questions/5452655/
#   python-regex-to-match-text-in-single-quotes-
#   ignoring-escaped-quotes-and-tabs-n

# quoted list values not at end of line
_SQ_L_VALUE = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'")
_DQ_L_VALUE = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
# quoted values with ignored trailing comments
_SQ_VALUE = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'(?:\s*(?:\#.*)?)?$")
_DQ_VALUE = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"(?:\s*(?:\#.*)?)?$')

_UQLP = re.compile(r"""(['"]?)(.*?)\1(,|$)""")
_SQV = re.compile("((?:^[^']*(?:'[^']*')*[^']*)*)(#.*)$")
_DQV = re.compile('((?:^[^"]*(?:"[^"]*")*[^"]*)*)(#.*)$')

# Paramterized names containing at least one comma.
REC_MULTI_PARAM = re.compile(r'<[\w]+,.*?>')


class ValidationError(ParsecError):
    pass


class ListValueError(ValidationError):
    def __init__(self, keys, value, exc=None):
        self.msg = (
            "ERROR: names containing commas must be quoted"
            " (e.g. 'foo<m,n>'):\n   %s" % itemstr(keys, value=value))
        if exc:
            self.msg += ": %s" % exc


class IllegalValueError(ValidationError):
    def __init__(self, vtype, keys, value, exc=None):
        self.msg = 'Illegal %s value: %s' % (vtype, itemstr(keys, value=value))
        if exc:
            self.msg += ": %s" % exc


class IllegalItemError(ValidationError):
    def __init__(self, keys, key, msg=None):
        if msg is not None:
            self.msg = 'Illegal item (%s): %s' % (msg, itemstr(keys, key))
        else:
            self.msg = 'Illegal item: %s' % itemstr(keys, key)


def validate(cfig, spec, keys=[]):
    """Validate and coerce a nested dict against a parsec spec."""
    for key, val in cfig.items():
        if key not in spec:
            if '__MANY__' not in spec:
                raise IllegalItemError(keys, key)
            else:
                # only accept the item if it's value is of the same type
                # as that of the __MANY__  item, i.e. dict or not-dict.
                val_is_dict = isinstance(val, dict)
                spc_is_dict = isinstance(spec['__MANY__'], dict)
                if not val_is_dict and '  ' in key:
                    # Item names shouldn't have consec. spaces (GitHub #2417).
                    raise IllegalItemError(keys, key, 'consecutive spaces')
                if (val_is_dict and spc_is_dict) or \
                        (not val_is_dict and not spc_is_dict):
                    speckey = '__MANY__'
                else:
                    raise IllegalItemError(keys, key)
        else:
            speckey = key
        specval = spec[speckey]
        if isinstance(val, dict) and isinstance(specval, dict):
            validate(val, spec[speckey], keys + [key])
        elif val is not None and not isinstance(specval, dict):
            # (if val is null we're only checking item validity)
            cfig[key] = spec[speckey].check(val, keys + [key])
        else:
            # raise IllegalItemError(keys, key)
            # THIS IS OK: blank value
            # TODO - ANY OTHER POSSIBILITIES?
            # print 'VAL:', val, '::', keys + [key]
            pass


def check_compulsory(cfig, spec, keys=[]):
    """Check compulsory items are defined in cfig."""
    for key, val in spec.items():
        if isinstance(val, dict):
            check_compulsory(cfig, spec[key], keys + [key])
        else:
            if val.args['compulsory']:
                cfg = cfig
                try:
                    for k in keys + [key]:
                        cfg = cfg[k]
                except KeyError:
                    # TODO - raise an exception
                    print >> sys.stderr, (
                        "COMPULSORY ITEM MISSING", keys + [key])


def _populate_spec_defaults(defs, spec):
    """Populate a nested dict with default values from a spec."""
    for key, val in spec.items():
        if isinstance(val, dict):
            if key not in defs:
                defs[key] = OrderedDictWithDefaults()
            _populate_spec_defaults(defs[key], spec[key])
        else:
            defs[key] = spec[key].args['default']


def get_defaults(spec):
    """Return a nested dict of default values from a parsec spec."""
    defs = OrderedDictWithDefaults()
    _populate_spec_defaults(defs, spec)
    return defs


def expand(sparse, spec):
    # get dense defaults
    dense = get_defaults(spec)
    # override defaults with sparse values
    m_override(dense, sparse)
    un_many(dense)
    return dense


_MULTI_LINE_SINGLE = re.compile(
    r"\A'''(.*?)'''\s*(?:#.*)?\Z", re.MULTILINE | re.DOTALL)
_MULTI_LINE_DOUBLE = re.compile(
    r'\A"""(.*?)"""\s*(?:#.*)?\Z', re.MULTILINE | re.DOTALL)


def _strip_and_unquote(keys, value):
    if value[:3] == "'''":
        m = re.match(_MULTI_LINE_SINGLE, value)
        if m:
            value = m.groups()[0]
        else:
            raise IllegalValueError("string", keys, value)

    elif value[:3] == '"""':
        m = re.match(_MULTI_LINE_DOUBLE, value)
        if m:
            value = m.groups()[0]
        else:
            raise IllegalValueError("string", keys, value)

    elif value.startswith('"'):
        m = _DQ_VALUE.match(value)
        if m:
            value = m.groups()[0]
        else:
            raise IllegalValueError("string", keys, value)

    elif value.startswith("'"):
        m = _SQ_VALUE.match(value)
        if m:
            value = m.groups()[0]
        else:
            raise IllegalValueError("string", keys, value)
    else:
        # unquoted
        value = value.split(r'#', 1)[0]

    # Note strip() removes leading and trailing whitespace, including
    # initial newlines on a multiline string:
    return value.strip()


def _unquoted_list_parse(keys, value):
    # http://stackoverflow.com/questions/4982531/
    # how-do-i-split-a-comma-delimited-string-in-python-except-
    # for-the-commas-that-are

    # First detect multi-parameter lists like <m,n>.
    if REC_MULTI_PARAM.search(value):
        raise ListValueError(keys, value)

    pos = 0
    while True:
        m = _UQLP.search(value, pos)
        result = m.group(2).strip()
        separator = m.group(3)
        yield result
        if not separator:
            break
        pos = m.end(0)


def _strip_and_unquote_list(keys, value):
    if value.startswith('"'):
        # double-quoted values
        m = _DQV.match(value)
        if m:
            value = m.groups()[0]
        values = _DQ_L_VALUE.findall(value)
    elif value.startswith("'"):
        # single-quoted values
        m = _SQV.match(value)
        if m:
            value = m.groups()[0]

        values = _SQ_L_VALUE.findall(value)
    else:
        # unquoted values (may contain internal quoted strings with list
        # delimiters inside 'em!)
        for quote, rec in (('"', _DQV), ("'", _SQV)):
            if quote in value:
                match = rec.match(value)
                if match:
                    value = match.groups()[0]
                    break
        else:
            value = value.split(r'#', 1)[0].strip()
        values = list(_unquoted_list_parse(keys, value))
        # allow trailing commas
        if values[-1] == '':
            values = values[0:-1]

    return values


def _coerce_str(value, keys, args):
    """Coerce value to a string."""
    if isinstance(value, list):
        # handle graph string merging
        vraw = []
        for v in value:
            vraw.append(_strip_and_unquote(keys, v))
        value = '\n'.join(vraw)
    else:
        value = _strip_and_unquote(keys, value)
    return value


def _coerce_int(value, keys, args):
    """Coerce value to an integer."""
    value = _strip_and_unquote(keys, value)
    if value in ['', None]:
        return None
    try:
        return int(value)
    except ValueError:
        raise IllegalValueError('int', keys, value)


def _coerce_float(value, keys, args):
    """Coerce value to a float."""
    value = _strip_and_unquote(keys, value)
    if value in ['', None]:
        return None
    try:
        return float(value)
    except ValueError:
        raise IllegalValueError('float', keys, value)


def _coerce_boolean(value, keys, args):
    """Coerce value to a boolean."""
    value = _strip_and_unquote(keys, value)
    if value in ['True', 'true']:
        return True
    elif value in ['False', 'false']:
        return False
    elif value in ['', None]:
        return None
    else:
        raise IllegalValueError('boolean', keys, value)


def _coerce_str_list(value, keys, args):
    """Coerce value to a list of strings."""
    return _strip_and_unquote_list(keys, value)


def _expand_list(values, keys, type_, allow_zeroes):
    lvalues = []
    for item in values:
        try:
            mult, val = item.split('*')
        except ValueError:
            # too few values to unpack: no multiplier
            try:
                lvalues.append(type_(item))
            except ValueError as exc:
                raise IllegalValueError("list", keys, item, exc)
        else:
            # mult * val
            try:
                lvalues += int(mult) * [type_(val)]
            except ValueError as exc:
                raise IllegalValueError("list", keys, item, exc)

    if not allow_zeroes:
        if type_(0.0) in lvalues:
            raise IllegalValueError("no-zero list", keys, values)

    return lvalues


def _coerce_int_list(value, keys, args):
    "Coerce list values with optional multipliers to integer."
    values = _strip_and_unquote_list(keys, value)
    return _expand_list(values, keys, int, args['allow zeroes'])


def _coerce_float_list(value, keys, args):
    "Coerce list values with optional multipliers to float."
    values = _strip_and_unquote_list(keys, value)
    return _expand_list(values, keys, float, args['allow zeroes'])


coercers = {
    'boolean': _coerce_boolean,
    'string': _coerce_str,
    'integer': _coerce_int,
    'float': _coerce_float,
    'string_list': _coerce_str_list,
    'integer_list': _coerce_int_list,
    'float_list': _coerce_float_list}


class validator(object):

    __slots__ = ['coercer', 'args']

    def __init__(self, vtype='string', default=None, options=[],
                 allow_zeroes=True, compulsory=False):
        self.coercer = coercers[vtype]
        self.args = {
            'options': options,
            'default': default,
            'allow zeroes': allow_zeroes,
            'compulsory': compulsory}

    def check(self, value, keys):
        value = self.coercer(value, keys, self.args)
        # handle option lists centrally here
        if self.args['options']:
            if isinstance(value, list):
                for val in value:
                    if val not in self.args['options']:
                        raise IllegalValueError('option', keys, val)
            else:
                if value not in self.args['options']:
                    raise IllegalValueError('option', keys, value)
        return value

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
"""Utility functions for printing and manipulating PARSEC NESTED DICTS.

The copy and override functions below assume values are either dicts
(nesting) or shallow collections of simple types.
"""

from io import StringIO
from copy import copy
import sys

from parsec.OrderedDict import OrderedDictWithDefaults


def intlistjoin(lst):
    """Return dump string for int list.

    Attempt grouping on sequences with 3 or more numbers:
    * Consider sequential int values in list, group them together in
      `START..END[..STEP]` syntax where relevant.
    * Consider same numbers in list, group them together in `N*INT` syntax.

    Arguments:
        lst (list): a list of int numbers.

    Return (str):
        The (hopefully) nicely formatted dump string.

    Examples:
        >>> intlistjoin([])
        ''
        >>> intlistjoin([10])
        '10'
        >>> intlistjoin([10, 10])
        '10, 10'
        >>> intlistjoin([10, 10, 10])
        '3*10'
        >>> intlistjoin([10, 11])
        '10, 11'
        >>> intlistjoin([10, 11, 12])
        '10..12'
        >>> intlistjoin([-1, 1, 3, 5, 0, 0, 0, 8, 9, 11, -1, 0, 1, 2])
        '-1..5..2, 3*0, 8, 9, 11, -1..2'
        >>> intlistjoin([-1, 1, 3, 5, 0, 0, 0, 8, 9, 11, 11, 12])
        '-1..5..2, 3*0, 8, 9, 11, 11, 12'
        >>> intlistjoin(
        ...     [-10, -10, -1, 1, 3, 5, 0, 0, 0, 8, 9, 11, -1, 0, 1, 2])
        '-10, -10, -1..5..2, 3*0, 8, 9, 11, -1..2'
        >>> intlistjoin(
        ...     [64747, -10, -10, -10, -1, 1, 3, 5, 0, 0, 0, 8, 9, 11, -1, 0,
        ...      1, 2, 3, 4, 19, 19, 19, 20, 20, 20, 21, 22, 23])
        '64747, 3*-10, -1..5..2, 3*0, 8, 9, 11, -1..4, 3*19, 3*20, 21..23'
    """
    rets = []
    items = list(lst)
    while items:
        group = [items.pop(0)]
        while items:
            if (len(group) == 1 or
                    items[0] - group[-1] == group[-1] - group[-2]):
                group.append(items.pop(0))
            else:
                # If 2 numbers only, return 1 back if grouping still possible
                # in subsequent lots.
                if len(group) == 2 and len(items) >= 2:
                    items.insert(0, group.pop())
                break
        if len(group) <= 2:
            # Less than 2 numbers
            rets += [str(item) for item in group]
        elif group[1] - group[0] > 1:
            # Sequence of numbers with equal steps > 1
            rets.append(
                '%d..%d..%d' % (group[0], group[-1], group[1] - group[0]))
        elif group[1] - group[0] == 1:
            # Sequence of incremental numbers
            rets.append('%d..%d' % (group[0], group[-1]))
        else:
            # Sequence of same number
            rets.append('%d*%d' % (len(group), group[0]))
    return ', '.join(rets)


def listjoin(lst, none_str=''):
    """Return string from joined list.

    Quote all elements if any of them contain comment or list-delimiter
    characters (currently quoting must be consistent across all elements).

    Note: multi-line values in list is not handle.
    """
    if not lst:
        # empty list
        return none_str
    if len(lst) > 2 and all(isinstance(item, int) for item in lst):
        return intlistjoin(lst)
    items = []
    for item in lst:
        if item is None:
            items.append(none_str)
        elif any(char in str(item) for char in ',#"\''):
            items.append(repr(item))  # will be quoted
        else:
            items.append(str(item))
    return ', '.join(items)


def printcfg(cfg, level=0, indent=0, prefix='', none_str='',
             handle=sys.stdout):
    """Pretty-print a parsec config item or section (nested dict).

    As returned by parse.config.get().
    """
    stack = [("", cfg, level, indent)]
    while stack:
        key_i, cfg_i, level_i, indent_i = stack.pop()
        spacer = " " * 4 * (indent_i - 1)
        if isinstance(cfg_i, dict):
            if not cfg_i and none_str is None:
                # Don't print empty sections if none_str is None. This does not
                # handle sections with no items printed because the values of
                # all items are empty or None.
                continue
            if key_i and level_i:
                # Print heading
                msg = "%s%s%s%s%s\n" % (
                    prefix, spacer, '[' * level_i, str(key_i), ']' * level_i)
                if not isinstance(handle, StringIO) and 'b' in handle.mode:
                    msg = msg.encode()
                handle.write(msg)

            # Nested sections are printed after normal settings
            subsections = []
            values = []
            for key, item in cfg_i.items():
                if isinstance(item, dict):
                    subsections.append((key, item, level_i + 1, indent_i + 1))
                else:
                    values.append((key, item, level_i + 1, indent_i + 1))

            stack += reversed(subsections)
            stack += reversed(values)
        else:
            key = ""
            if key_i:
                key = "%s = " % key_i
            if cfg_i is None:
                value = none_str
            elif isinstance(cfg_i, list):
                value = listjoin(cfg_i, none_str)
            elif "\n" in str(cfg_i) and key:
                value = '"""\n'
                for line in str(cfg_i).splitlines(True):
                    value += spacer + " " * 4 + line
                value += '\n' + spacer + '"""'
            else:
                value = str(cfg_i)
            if value is not None:
                msg = "%s%s%s%s\n" % (prefix, spacer, key, value)
                if not isinstance(handle, StringIO) and 'b' in handle.mode:
                    msg = msg.encode()
                handle.write(msg)


def replicate(target, source):
    """Replicate source *into* target.

    Source elements need not exist in target already, so source overrides
    common elements in target and otherwise adds elements to it.
    """
    if not source:
        return
    if hasattr(source, "defaults_"):
        target.defaults_ = pdeepcopy(source.defaults_)
    for key, val in source.items():
        if isinstance(val, dict):
            if key not in target:
                target[key] = OrderedDictWithDefaults()
            if hasattr(val, 'defaults_'):
                target[key].defaults_ = pdeepcopy(val.defaults_)
            replicate(target[key], val)
        elif isinstance(val, list):
            target[key] = val[:]
        else:
            target[key] = val


def pdeepcopy(source):
    """Make a deep copy of a pdict source"""
    target = OrderedDictWithDefaults()
    replicate(target, source)
    return target


def poverride(target, sparse, prepend=False):
    """Override or add items in a target pdict.

    Target sub-dicts must already exist. For keys that already exist in the
    target, the value is overridden in-place. New keys can be prepended in the
    target (Cylc use case: broadcast environment variables should be defined
    first in the user environment section, to allow use in subsequent variable
    definitions.

    """
    if not sparse:
        return
    for key, val in sparse.items():
        if isinstance(val, dict):
            poverride(target[key], val, prepend)
        else:
            if prepend and (key not in target):
                # Prepend new items in the target ordered dict.
                setitem = target.prepend
            else:
                # Override in-place in the target ordered dict.
                setitem = target.__setitem__
            if isinstance(val, list):
                setitem(key, val[:])
            else:
                setitem(key, val)


def m_override(target, sparse):
    """Override items in a target pdict.

    Target keys must already exist unless there is a "__MANY__" placeholder in
    the right position.
    """
    if not sparse:
        return
    stack = [(sparse, target, [], OrderedDictWithDefaults())]
    defaults_list = []
    while stack:
        source, dest, keylist, many_defaults = stack.pop(0)
        if many_defaults:
            defaults_list.append((dest, many_defaults))
        for key, val in source.items():
            if isinstance(val, dict):
                if key in many_defaults:
                    child_many_defaults = many_defaults[key]
                else:
                    child_many_defaults = OrderedDictWithDefaults()
                if key not in dest:
                    if '__MANY__' in dest:
                        dest[key] = OrderedDictWithDefaults()
                        child_many_defaults = dest['__MANY__']
                    elif '__MANY__' in many_defaults:
                        # A 'sub-many' dict - would it ever exist in real life?
                        dest[key] = OrderedDictWithDefaults()
                        child_many_defaults = many_defaults['__MANY__']
                    elif key in many_defaults:
                        dest[key] = OrderedDictWithDefaults()
                    else:
                        # TODO - validation prevents this, but handle properly
                        # for completeness.
                        raise Exception(
                            "parsec dict override: no __MANY__ placeholder" +
                            "%s" % (keylist + [key])
                        )
                stack.append(
                    (val, dest[key], keylist + [key], child_many_defaults))
            else:
                if key not in dest:
                    if ('__MANY__' in dest or key in many_defaults or
                            '__MANY__' in many_defaults):
                        if isinstance(val, list):
                            dest[key] = val[:]
                        else:
                            dest[key] = val

                    else:
                        # TODO - validation prevents this, but handle properly
                        # for completeness.
                        raise Exception(
                            "parsec dict override: no __MANY__ placeholder" +
                            "%s" % (keylist + [key])
                        )
                if isinstance(val, list):
                    dest[key] = val[:]
                else:
                    dest[key] = val
    for dest_dict, defaults in defaults_list:
        dest_dict.defaults_ = defaults


def un_many(cfig):
    """Remove any '__MANY__' items from a nested dict, in-place."""
    if not cfig:
        return
    for key, val in list(cfig.items()):
        if key == '__MANY__':
            try:
                del cfig[key]
            except KeyError:
                if hasattr(cfig, 'defaults_') and key in cfig.defaults_:
                    del cfig.defaults_[key]
                else:
                    raise
        elif isinstance(val, dict):
            un_many(cfig[key])


def itemstr(parents=None, item=None, value=None):
    """
    Pretty-print an item from list of sections, item name, and value
    E.g.: ([sec1, sec2], item, value) to '[sec1][sec2]item = value'.
    """
    if parents:
        keys = copy(parents)
        if value and not item:
            # last parent is the item
            item = keys[-1]
            keys.remove(item)
        text = '[' + ']['.join(keys) + ']'
    else:
        text = ''
    if item:
        text += str(item)
        if value:
            text += " = " + str(value)
    if not text:
        text = str(value)

    return text


if __name__ == "__main__":
    print('Item strings:')
    print('  ', itemstr(['sec1', 'sec2'], 'item', 'value'))
    print('  ', itemstr(['sec1', 'sec2'], 'item'))
    print('  ', itemstr(['sec1', 'sec2']))
    print('  ', itemstr(['sec1']))
    print('  ', itemstr(item='item', value='value'))
    print('  ', itemstr(item='item'))
    print('  ', itemstr(value='value'))
    # error or useful?
    print('  ', itemstr(parents=['sec1', 'sec2'], value='value'))

    print('Configs:')
    printcfg('foo', prefix=' > ')
    printcfg(['foo', 'bar'], prefix=' > ')
    printcfg({}, prefix=' > ')
    printcfg({'foo': 1}, prefix=' > ')
    printcfg({'foo': None}, prefix=' > ')
    printcfg({'foo': None}, none_str='(none)', prefix=' > ')
    printcfg({'foo': {'bar': 1}}, prefix=' > ')
    printcfg({'foo': {'bar': None}}, prefix=' > ')
    printcfg({'foo': {'bar': None}}, none_str='(none)', prefix=' > ')
    printcfg({'foo': {'bar': 1, 'baz': 2, 'qux': {'boo': None}}},
             none_str='(none)', prefix=' > ')

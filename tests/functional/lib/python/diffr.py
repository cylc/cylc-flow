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
"""Quick and simple JSON diff util.

Examples:
    >>> bool(Diff({}, {}))
    True

    >>> diff = Diff({'a': 1, 'b': 2},
    ...             {'b': 3, 'd': 4})
    >>> bool(diff)
    False
    >>> list(diff.added())
    [(['d'], 4)]
    >>> list(diff.removed())
    [(['a'], 1)]
    >>> list(diff.modified())
    [(['b'], 2, 3)]

    >>> diff = Diff({'x': {'y': {'z': 1}}},
    ...             {'x': {'y': {'z': 2}}})
    >>> list(diff.modified())
    [(['x', 'y', 'z'], 1, 2)]

"""
import argparse
import json
import sys
from typing import Callable, Optional, Tuple, Type


class Diff:
    """Representation of a diff between two dictionaries."""

    BRACES = {
        dict: ('{', '}'),
        list: ('[', ']')
    }

    def __init__(self, this, that, this_name='expected', that_name='got'):
        self.typ, self.changed = self.compute_diff(this, that)
        self.this_name = this_name
        self.that_name = that_name

    @classmethod
    def _diff_method(
        cls, this: object, that: object
    ) -> Tuple[Optional[Type], Optional[Callable]]:
        if isinstance(this, list) and isinstance(that, list):
            return list, cls.diff_list
        if isinstance(this, dict) and isinstance(that, dict):
            return dict, cls.diff_dict
        return None, None

    @classmethod
    def compute_diff(cls, this, that):
        """Return a list of differences between this and that.

        Entries take the form::
            (symbol, (key, *value))

        Where:
            symbol:
               * ``+``: for items in that but not in this.
               * ``-``: for items in this but not in that.
               * ``?``: for items common to both but with different values.
            key:
               * ``dict``: The key of a key, value pair.
               * ``list``: The index of an element.
            value:
               A tuple containing information about the change:

               * ``+ (key, value)``
               * ``- (key, value)``
               * ``? (key, this_value, that_value)``

        """
        typ, meth = cls._diff_method(this, that)
        if meth:
            return typ, meth(this, that)
        raise TypeError('%s Cannot compare %s and %s' % (
            cls.__name__, type(this), type(that)))

    @classmethod
    def diff_list(cls, this, that):
        """Return differences between two lists.

        So unsurprisingly differencing nested lists is actually a little
        tricky so this is the simple and crude method, just mark the items as
        modified rather than going through the mess of working out how the
        lists could fit together.

        """
        changed = []
        for index, (this_item, that_item) in enumerate(zip(this, that)):
            if this_item != that_item:
                if cls._diff_method(this_item, that_item):
                    changed.append((index, cls(this_item, that_item)))
                else:
                    changed.append(('?', (index, this_item, that_item)))

        if len(this) > len(that):
            symbol = '-'
            additional = this
        else:
            symbol = '+'
            additional = that

        for index in range(min(len(this), len(that)),
                           max(len(this), len(that))):
            changed.append((symbol, (index, additional[index],)))

        return changed

    @classmethod
    def diff_dict(cls, this, that):
        """Return differences between two dictionaries.

        As this is a JSON comparison tool ignore the order of keys.

        """
        changed = []
        for key, value in that.items():
            if key not in this:
                changed.append(('+', (key, value)))
            elif isinstance(value, (dict, list)):
                if cls._diff_method(this[key], that[key]):
                    this[key] = cls(this[key], that[key])
                    if this[key].changed:
                        changed.append((key, this[key]))
                else:
                    changed.append(('?', (key, this[key], value)))
            elif value != this[key]:
                changed.append(('?', (key, this[key], value)))
        for key, value in this.items():
            if key not in that:
                changed.append(('-', (key, value)))
        return changed

    def __str__(self):
        return self.tostr()

    def tostr(self, indent=0):
        """Return unified(ish) diff."""
        ret = ''

        if indent == 0:
            ret += '--- %s\n' % self.this_name
            ret += '+++ %s\n' % self.that_name
            ret += '============\n'
            ret += ' %s\n' % self.BRACES[self.typ][0]

        pre = '    ' * indent
        for itt, (symbol, item) in enumerate(self.changed):
            post = ''
            if itt != len(self.changed) - 1:
                post = ','

            if isinstance(item, Diff):
                diff = item
                key = symbol
                ret += ' %s %s: %s\n' % (pre, key, self.BRACES[diff.typ][0])
                ret += diff.tostr(indent + 1)
                ret += ' %s %s%s\n' % (pre, self.BRACES[diff.typ][1], post)
            else:
                if symbol == '?':
                    key, before, after = item
                    ret += f'{symbol}{pre} {key}: {before} => {after}{post}\n'
                elif symbol in ['+', '-']:
                    if len(item) == 2:
                        value = '%s: %s' % item
                    else:
                        value = item[0]
                    ret += f'{symbol}{pre} {value}{post}\n'

        if indent == 0:
            ret += ' %s\n' % self.BRACES[self.typ][1]

        return ret

    def added(self):
        """Yield items present in this but not in that as (key, value)."""
        yield from self._filter('+')

    def removed(self):
        """Yield items present in that but not in this as (key, value)."""
        yield from self._filter('-')

    def modified(self):
        """Yield items change as (key, this_value, that_value)."""
        yield from self._filter('?')

    def _filter(self, *symbols):
        """Filter items by change status (+,-,?)."""
        for symbol, item in self.changed:
            if symbol in symbols:
                yield ([item[0]], *item[1:])
            elif isinstance(item, Diff):
                yield from (([symbol, *res[0]], *res[1:])
                            for res in item.filter(*symbols))

    def __bool__(self):
        return not bool(self.changed)

    def __len__(self):
        return len(self.changed)


def load_json(file1, file2=None):
    """Read in JSON, return python data structure.

    If file2 is None read from sys.stdin

    """
    try:
        this = json.loads(file1)
    except json.decoder.JSONDecodeError as exc:
        sys.exit(f'Syntax error in file1: {exc}')

    try:
        if file2:
            that = json.loads(file2)
        else:
            that = json.load(sys.stdin)
    except json.decoder.JSONDecodeError as exc:
        sys.exit(f'Syntax error in file2: {exc}')

    return this, that


def parse_args():
    """Return CLI args."""
    parser = argparse.ArgumentParser()
    parser.add_argument('file1')
    parser.add_argument('file2', nargs='?')

    parser.add_argument(
        '-1', action='store', dest='name1', default='expected', help=(
            'name file 1, default=expected'))
    parser.add_argument(
        '-2', action='store', dest='name2', default='got', help=(
            'name file 2, default=got'))

    parser.add_argument(
        '-c1', '--contains1', action='store_const', const=1, default=0,
        dest='contains', help=(
            'test all (key, value) pairs in file1 are in file2'))
    parser.add_argument(
        '-c2', '--contains2', action='store_const', const=2, default=0,
        dest='contains', help=(
            'test all (key, value) pairs in file2 are in file1'))

    parser.add_argument(
        '--color', '--colour', action='store', default='never', help=(
            'Use color? Option in always, never'), dest='color')

    args = parser.parse_args()

    return args


def main(args):
    """Implement dictdiff."""
    this, that = load_json(args.file1, args.file2)

    if this == that:
        # skip all diff logic if possible
        sys.exit(0)

    if args.contains:
        # test if items from one file present in the other
        if args.contains == 2:
            this, that = that, this
            args.name1, args.name2 = args.name2, args.name1
        diff = Diff(this, that, args.name1, args.name2)
        for _ in diff._filter('-', '?'):
            sys.stderr.write(str(diff))
            sys.exit(1)
        sys.exit(0)

    diff = Diff(this, that, args.name1, args.name2)
    if diff:
        sys.exit(0)
    else:
        sys.stderr.write(str(diff))
        sys.exit(len(diff))


if __name__ == '__main__':
    main(parse_args())

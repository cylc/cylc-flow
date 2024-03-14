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
"""Misc functionality."""

from contextlib import suppress
from functools import partial
import json
import re
from typing import (
    Any,
    List,
    Sequence,
)


_NAT_SORT_SPLIT = re.compile(r'([\d\.]+)')


def natural_sort_key(key: str, fcns=(int, str)) -> List[Any]:
    """Returns a key suitable for sorting.

    Splits the key into sortable chunks to preserve numerical order.

    Examples:
        >>> natural_sort_key('a1b2c3')
        ['a', 1, 'b', 2, 'c', 3]
        >>> natural_sort_key('a123b')
        ['a', 123, 'b']
        >>> natural_sort_key('a1.23b', fcns=(float, str))
        ['a', 1.23, 'b']
        >>> natural_sort_key('a.b')
        ['a', '.', 'b']

    """
    ret = []
    for item in _NAT_SORT_SPLIT.split(key):
        for fcn in fcns:
            with suppress(TypeError, ValueError):
                ret.append(fcn(item))
                break
    if ret[-1] == '':
        ret.pop(-1)
    return ret


def natural_sort(items: List[str], fcns=(int, str)) -> None:
    """Sorts a list preserving numerical order.

    Note this is an in-place sort.

    Examples:
        >>> lst = ['a10', 'a1', 'a2']
        >>> natural_sort(lst)
        >>> lst
        ['a1', 'a2', 'a10']

        >>> lst = ['a1', '1a']
        >>> natural_sort(lst)
        >>> lst
        ['1a', 'a1']

    """
    items.sort(key=partial(natural_sort_key, fcns=fcns))


def format_cmd(cmd: Sequence[str], maxlen: int = 60) -> str:
    r"""Convert a shell command list to a user-friendly representation.

    Examples:
        >>> format_cmd(['echo', 'hello', 'world'])
        'echo hello world'
        >>> format_cmd(['echo', 'hello', 'world'], 5)
        'echo \\ \n    hello \\ \n    world'

    """
    ret = []
    line = cmd[0]
    for part in cmd[1:]:
        if line and (len(line) + len(part) + 3) > maxlen:
            ret.append(line)
            line = part
        else:
            line += f' {part}'
    if line:
        ret.append(line)
    return ' \\ \n    '.join(ret)


def cli_format(cmd: List[str]):
    """Format a command list as it would appear on the command line.

    I.E. put spaces between the items in the list.

    BACK_COMPAT: cli_format
        From:
            Python 3.7
        To:
            Python 3.8
        Remedy:
            Can replace with shlex.join

    Examples:
        >>> cli_format(['sleep', '10'])
        'sleep 10'

    """
    return ' '.join(cmd)


def serialise(flow_nums: set):
    """Convert set to json.
    For use when a sorted result is needed for consistency.
    Example:
    >>> serialise({'3','2'})
    '["2", "3"]'
"""
    return json.dumps(sorted(flow_nums))


def deserialise(flow_num_str: str):
    """Converts string to set."""
    return set(json.loads(flow_num_str))

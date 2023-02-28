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
    Tuple,
    Union,
    Optional,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from optparse import OptionParser, Values
    from cylc.flow.option_parsers import OptionSettings


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


def format_parsed_opts(
    parser: 'OptionParser',
    cmd: List[str],
    options: 'Values',
    arguments: List[str],
    opt_filter: 'Optional[List[OptionSettings]]' = None,
    width: Optional[int] = None,
    ps1: str = '',
) -> str:
    """Format parsed options as they would have appeared on the CLI.

    Effectively the reverse of OptionParser.parse_args.

    Args:
        parser:
            The argument parser used to parse the options.
        cmd:
            The command being parsed e.g. ['cylc', 'validate'].
        options:
            The parsed options i.e. OptionParser.parse_args[0].
        arguments:
            The parsed arguments i.e. OptionParser.parse_args[1].
        opt_filter:
            If present, only options which are present in this
            list will be included in the output.
        width:
            The max width of each line of the formatted command.
            I.E. the width of the terminal you are writing to.

    Returns:
        A string, potentially containing newlines.

    """
    _cmd = get_parsed_opts(parser, options, opt_filter=opt_filter)
    return format_cmd([*cmd, *_cmd, *arguments], maxlen=width or 60, ps1=ps1)


def get_parsed_opts(
    parser: 'OptionParser',
    options: 'Values',
    opt_filter: 'Optional[List[OptionSettings]]' = None,
) -> List[str]:
    """Return parsed options as a list of the CLI strings that preceded them.

    This is the reverse of OptionParser.parse_args, it gives you the CLI
    strings which would have been required to produce the given options,

    See format_parsed_opts for details.

    Note:
        This does not support all optparse options e.g. decrement & increment.
        Anything it can't handle will be ignored.

    """
    ret: List[str] = []
    filter_dests: Optional[List[str]] = None
    if opt_filter:
        filter_dests = [
            option.kwargs.get('dest', option.args[0].replace('--', '').replace('-', '_'))
            for option in opt_filter
        ]
    for option in parser._get_all_options():
        if not option.dest:
            continue
        if filter_dests is not None and option.dest not in filter_dests:
            continue
        value = getattr(options, option.dest)
        if value and value == option.default:
            continue
        if option.action in {'store'}:
            if value:
                ret.append(option.get_opt_string())
                ret.append(value)
        if option.action in {'store_true'}:
            if value and option.default in {('NO', 'DEFAULT'), False}:
                ret.append(option.get_opt_string())
        if option.action in {'store_false'}:
            if not value and option.default is True:
                ret.append(option.get_opt_string())
        if option.action in {'append'}:
            for item in value or []:
                ret.extend([
                    option.get_opt_string(),
                    item
                ])
    return ret


def format_cmd(cmd: Union[List[str], Tuple[str]], maxlen: int = 60, ps1='') -> str:
    r"""Convert a shell command list to a user-friendly representation.

    Examples:
        >>> format_cmd(['echo', 'hello', 'world'])
        'echo hello world'
        >>> format_cmd(['echo', 'hello', 'world'], 5)
        'echo \\ \n    hello \\ \n    world'
        >>> format_cmd(['/usr/bin/true', 'to', 'your', 'heart'], ps1='$ ')
        '$ /usr/bin/true to your heart'

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
    return ps1 + ' \\ \n    '.join(ret)


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

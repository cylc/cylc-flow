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

import re


REC_CONDITIONALS = re.compile("([&|()])")


def listify(message):
    """Convert a string containing a logical expression to a list

    Examples:
        >>> listify('(foo)')
        ['foo']

        >>> listify('foo & (bar | baz)')
        ['foo', '&', ['bar', '|', 'baz']]

        >>> listify('(a&b)|(c|d)&(e|f)')
        [['a', '&', 'b'], '|', ['c', '|', 'd'], '&', ['e', '|', 'f']]

        >>> listify('a & (b & c)')
        ['a', '&', ['b', '&', 'c']]

        >>> listify('a & b')
        ['a', '&', 'b']

        >>> listify('a & (b)')
        ['a', '&', 'b']

        >>> listify('((foo)')
        Traceback (most recent call last):
        ValueError: ((foo)

        >>> listify('(foo))')
        Traceback (most recent call last):
        ValueError: (foo))

    """
    message = message.replace("'", "\"")

    ret_list = []
    stack = [ret_list]
    for item in REC_CONDITIONALS.split(message):
        item = item.strip()
        if item and item not in ["(", ")"]:
            stack[-1].append(item)
        elif item == "(":
            stack[-1].append([])
            stack.append(stack[-1][-1])
        elif item == ")":
            stack.pop()
            if not stack:
                raise ValueError(message)
            if isinstance(stack[-1][-1], list) and len(stack[-1][-1]) == 1:
                stack[-1][-1] = stack[-1][-1][0]
    if len(stack) > 1:
        raise ValueError(message)
    return ret_list

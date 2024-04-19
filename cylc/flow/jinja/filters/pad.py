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
"""Filter for padding strings to a set number of chars."""

from typing import Union


def pad(value: str, length: Union[int, str], fillchar: str = ' '):
    """Pads a string to some length with a fill character

    Useful for generating task names and related values in ensemble workflows.

    Args:
        value:
            The string to pad.
        length:
            The length for the returned string.
        fillchar:
            The character to fill in surplus space (space by default).

    Returns:
        str: value padded to the left with fillchar to length length.

    Python Examples:
        >>> pad('13', 3, '0')
        '013'
        >>> pad('foo', 6)
        '   foo'
        >>> pad('foo', 2)
        'foo'

    Jinja2 Examples:
        .. code-block:: cylc

           {% for i in range(0,100) %}  # 0, 1, ..., 99
               {% set j = i | pad(2,'0') %}
               [[A_{{j}}]]         # [[A_00]], [[A_01]], ..., [[A_99]]
           {% endfor %}

    """
    return str(value).rjust(int(length), str(fillchar))

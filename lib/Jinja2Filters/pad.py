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
"""Provides a Jinja2 filter for padding strings to a set number of chars."""


def pad(value, length, fillchar=' '):
    """Pads a string to some length with a fill character

    Args:
        value (str): The string to padd.
        length (int/str): The length for the returned string.
        fillchar (str - optional): The character to fill in surplus space
            (space by default).

    Returns:
        str: value padded to the left with fillchar to length length.

    Examples:
        >>> pad('13', 3, '0')
        '013'
        >>> pad('foo', 6)
        '   foo'
        >>> pad('foo', 2)
        'foo'

    """
    return str(value).rjust(int(length), str(fillchar))

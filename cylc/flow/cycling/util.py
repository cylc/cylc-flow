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
"""Cycling utility functions."""

from metomi.isodatetime.parsers import TimePointParser, DurationParser


def add_offset(cycle_point, offset, dmp_fmt=None):
    """Add a (positive or negative) offset to a cycle point.

    Return the result.

    """
    my_parser = TimePointParser()
    if dmp_fmt is None:
        my_target_point = my_parser.parse(cycle_point, dump_as_parsed=True)
    else:
        my_target_point = my_parser.parse(cycle_point, dump_format=dmp_fmt)
    my_offset_parser = DurationParser()

    oper = "+"
    if offset.startswith(("-", "+")):
        oper = offset[0]
        offset = offset[1:]

    if not offset.startswith("P"):
        # TODO - raise appropriate exception
        raise ValueError("ERROR, bad offset format: %s" % offset)

    my_shift = my_offset_parser.parse(offset)
    if oper == "-":
        my_target_point -= my_shift
    else:
        my_target_point += my_shift

    return my_target_point

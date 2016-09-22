#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

from cylc.cycling.loader import get_interval, get_interval_cls
from cylc.task_id import TaskID
import re

# Cylc's ISO 8601 format.
NODE_ISO_RE = re.compile(
    r"^" +
    r"(" + TaskID.NAME_RE + r")" +
    r"""(?:\[        # Begin optional [offset] syntax
         (?!T[+-])   # Do not match a 'T-' or 'T+' (this is the old format)
         ([^\]]+)    # Continue until next ']'
         \]          # Stop at next ']'
        )?           # End optional [offset] syntax]
        (:[\w-]+|)$  # Optional type (e.g. :succeed)
     """, re.X)

# Cylc's ISO 8601 initial cycle point based format
NODE_ISO_ICT_RE = re.compile(
    r"^" +
    r"(" + TaskID.NAME_RE + r")" +
    r"""\[           # Begin square bracket syntax
        \^           # Initial cycle point offset marker
        ([^\]]*)     # Optional ^offset syntax
        \]           # End square bracket syntax
        (:[\w-]+|)$  # Optional type (e.g. :succeed)
     """, re.X)

# A potentially non-regular offset, such as foo[01T+P1W].
IRREGULAR_OFFSET_RE = re.compile(
    r"""^            # Start of string
        (            # Begin group
         ..+         # EITHER: Two or more characters
         [+-]P       # Then either +P or -P for start of duration
         .*          # Then anything for the rest of the duration
         |           # OR:
         [^P]+       # No 'P' characters anywhere (e.g. T00).
        )            # End group
        $            # End of string
    """, re.X)


class GraphNodeError(Exception):
    """
    Attributes:
        message - what the problem is.
    """
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class graphnode(object):
    """A node in the cycle suite.rc dependency graph."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["offset_is_from_ict", "offset_is_irregular",
                 "is_absolute", "special_output", "output",
                 "name", "intercycle", "offset_string"]

    def __init__(self, node, base_interval=None):
        node_in = node
        # Get task name and properties from a graph node name.

        # Graph node name is task name optionally followed by:
        # - output label: foo:m1
        # - intercycle dependence: foo[T-6]
        # These may be combined: foo[T-6]:m1
        # Task may be defined at initial cycle point: foo[^]
        # or relative to initial cycle point: foo[^+P1D]

        self.offset_is_from_ict = False
        self.offset_is_irregular = False
        self.is_absolute = False

        m = re.match(NODE_ISO_ICT_RE, node)
        if m:
            # node looks like foo[^], foo[^-P4D], foo[^]:fail, etc.
            self.is_absolute = True
            name, offset_string, outp = m.groups()
            self.offset_is_from_ict = True
            sign = ""
            prev_format = False
            # Can't always set syntax here, as we use [^] for backwards comp.
        else:
            m = re.match(NODE_ISO_RE, node)
            if m:
                # node looks like foo, foo:fail, foo[-PT6H], foo[-P4D]:fail...
                name, offset_string, outp = m.groups()
                sign = ""
                prev_format = False
            else:
                raise GraphNodeError('Illegal graph node: ' + node)

        if outp:
            self.special_output = True
            self.output = outp[1:]  # strip ':'
        else:
            self.special_output = False
            self.output = None

        if name:
            self.name = name
        else:
            raise GraphNodeError('Illegal graph node: ' + node)

        if self.offset_is_from_ict and not offset_string:
            offset_string = str(get_interval_cls().get_null_offset())
        if offset_string:
            self.intercycle = True
            if prev_format:
                self.offset_string = str(
                    base_interval.get_inferred_child(offset_string))
            else:
                if IRREGULAR_OFFSET_RE.search(offset_string):
                    self.offset_string = offset_string
                    self.offset_is_irregular = True
                else:
                    self.offset_string = str(
                        (get_interval(offset_string)).standardise())
        else:
            self.intercycle = False
            self.offset_string = None

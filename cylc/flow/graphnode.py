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
"""Provide graph node parsing and caching service"""

import re

from cylc.flow.cycling.loader import (
    get_interval, get_interval_cls, is_offset_absolute)
from cylc.flow.exceptions import GraphParseError
from cylc.flow.task_id import TaskID
from cylc.flow.task_trigger import TaskTrigger


class GraphNodeParser:
    """Provide graph node parsing and caching service.

    Optional output notation is stripped out before this class gets used.
    TODO is any of this redundant with code in the graph_parser module?
    """
    # Match a graph node string.
    REC_NODE = re.compile(
        r"^" +
        r"(" + TaskID.NAME_RE + r")" +
        r"""(?:\[          # Begin optional [offset] syntax
             (?!T[+-])     # Do not match a 'T-' or 'T+'
                           # (this is the old format)
             (\^?)         # Initial cycle point offset marker
             ([^\]]*)      # Continue until next ']'
             \]            # Stop at next ']'
            )?             # End optional [offset] syntax]
            (?::([\w-]+))? # Optional output (e.g. :succeed)
            $
         """, re.X)

    # A potentially non-regular offset, such as foo[01T+P1W].
    REC_IRREGULAR_OFFSET = re.compile(
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

    _INSTANCE = None

    @classmethod
    def get_inst(cls):
        """Return the singleton instance."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self):
        self._offsets = {}
        self._nodes = {}

    def clear(self):
        """Clear caches."""
        self._offsets.clear()
        self._nodes.clear()

    def _get_offset(self, offset=None):
        """Return and cache the standardised offset string."""
        if offset not in self._offsets:
            if offset:
                res = get_interval(offset).standardise()
            else:
                res = get_interval_cls().get_null_offset()
            self._offsets[offset] = str(res)
        return self._offsets[offset]

    def parse(self, node):
        """Parse graph node, and cache the result.

        Args:
            node (str): node to parse

        Return:
            tuple:
            (name, offset, output,
            offset_is_from_icp, offset_is_irregular, offset_is_absolute)

        NOTE that offsets from ICP like foo[^] and foo[^+P1] are not considered
              absolute like foo[2] etc.

        Raise:
            GraphParseError: on illegal syntax.
        """
        if node not in self._nodes:
            match = self.REC_NODE.match(node)
            if not match:
                raise GraphParseError('Illegal graph node: %s' % node)
            name, icp_mark, offset, output = match.groups()
            offset_is_from_icp = (icp_mark == '^')  # convert to boolean
            if offset_is_from_icp and not offset:
                offset = self._get_offset()
            offset_is_irregular = False
            offset_is_absolute = False
            if offset:
                if is_offset_absolute(offset):
                    offset_is_absolute = True
                if self.REC_IRREGULAR_OFFSET.search(offset):
                    offset_is_irregular = True
                else:
                    offset = self._get_offset(offset)
            self._nodes[node] = (
                name, offset, TaskTrigger.standardise_name(output),
                offset_is_from_icp, offset_is_irregular, offset_is_absolute)
        return self._nodes[node]

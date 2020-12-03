# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

"""Functionality for evaluating Python safely."""

import ast


class SafeVisitor(ast.NodeVisitor):
    """Abstract syntax tree node visitor for whitelisted evaluations.

    Attribues:
        whitelisted_nodes (tuple):
            Collection of ast nodes that this visitor is permitted to visit.
        whitelisted_functions (tuple):
            Collection of function names that this visitor is permitted to
            call.

            Note that only functions provided to the "eval()" call are
            available to the visitor in the first place.

    Raises:
        ValueError:
            In the event that this visitor is asked to visit a non-whitelisted
            node or call a non-whitelisted function.

    """

    def visit(self, node):
        if not isinstance(node, self.whitelisted_nodes):
            # permit only whitelisted operations
            raise ValueError(type(node))
        if isinstance(node, ast.Call):
            func = getattr(node, 'func', None)
            if isinstance(func, ast.Name):
                if func.id not in self.whitelisted_functions:
                    raise ValueError(func.id)
            else:
                raise ValueError(node.func)
        elif isinstance(node, ast.Name):
            if node.id not in self.whitelisted_functions:
                raise ValueError(node.id)
        return super().visit(node)

    whitelisted_nodes = ()
    whitelisted_functions = ()

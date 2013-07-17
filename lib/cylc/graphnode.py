#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
OFFSET_RE =re.compile('(\w+)\s*\[\s*T\s*([+-]\s*\d+)\s*\]')

class GraphNodeError( Exception ):
    """
    Attributes:
        message - what the problem is. 
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class graphnode( object ):
    """A node in the cycle suite.rc dependency graph."""

    def __init__( self, node ):
        node_in = node
        # Get task name and properties from a graph node name.

        # Graph node name is task name optionally followed by:
        # - output label: foo:m1
        # - intercycle dependence: foo[T-6]
        # These may be combined: foo[T-6]:m1

        # Defaults:
        self.intercycle = False
        self.special_output = False

        self.offset = None # negative offset (e.g. foo[T-N] -> N)
        self.output = None

        # parse and strip special output: foo[T-6]:m1 -> foo[T-6]
        m = re.match( '(.*):([\w-]+)', node )
        if m:
            self.special_output = True
            node, self.output = m.groups()

        # parse and strip intercyle: foo[T-6] or foo[T-nd] --> foo
        m = re.match( OFFSET_RE, node )
        if m:
            self.intercycle = True
            node, offset = m.groups()
            # change sign to get self.offset:
            self.offset = str( -int( offset ))
        # only name left now
        self.name = node


#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

from cycling.loader import interval
import re
NODE_RE =re.compile('^(\w+)\s*(?:\[\s*T?\s*([+-]?)(\s*[,.\w]*)\s*\]){0,1}(:[\w-]+){0,1}$')


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

    def __init__( self, node, base_offset=None ):
        node_in = node
        # Get task name and properties from a graph node name.

        # Graph node name is task name optionally followed by:
        # - output label: foo:m1
        # - intercycle dependence: foo[T-6]
        # These may be combined: foo[T-6]:m1

        m = re.match( NODE_RE, node )
        if m:
            name, sign, offset, outp = m.groups()

            if outp:
                self.special_output = True
                self.output = outp[1:] # strip ':'
            else:
                self.special_output = False
                self.output = None

            if name:
                self.name = name
            else:
                raise GraphNodeError( 'Illegal graph node: ' + node )

            if offset:
                self.intercycle = True
                if sign == '+':
                    self.offset = - interval( offset )
                else:
                    self.offset = interval( offset )
                # TODO: Post-backward compatibility: remove try-except block.
                try:
                    self.offset.standardise()
                except ValueError:
                    # An invalid offset, probably in the prev format.
                    if base_offset is None:
                        raise
                    # If offset is '+24' & base_offset is 'P1D', infer 'P24D'.
                    self.offset = base_offset.get_inferred_child(offset)
            else:
                self.intercycle = False
                self.offset = None

        else:
            raise GraphNodeError( 'Illegal graph node: ' + node )

if __name__ == '__main__':
    # TODO ISO - this is only for integer cycling:
    nodes = [
        'foo[T-24]:outx',
        'foo[T-24]',
        'foo:outx',
        ':out1', # error
        '[T-24]', # error
        'outx:[T-24]', # error
        '[T-6]:outx', # error
        'foo:m1[T-24]' # error
        ]

    for n in nodes:
        print n, '...',
        m = re.match( NODE_RE, n )
        if m:
            print m.groups()
        else:
            print 'ERROR!'


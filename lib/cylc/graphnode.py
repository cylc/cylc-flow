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

from cycling.loader import get_interval, get_interval_cls
import flags
import re

# Previous node format.
NODE_PREV_RE = re.compile(
    r"""^(\w+)          # Task name
        \s*             # Optional whitespace
        (?:\[           # Begin optional [offset] syntax, start [
         \s*            # Optional whitespace
         T              # T as in T-6, T+1, etc
         \s*            # Optional whitespace
         ([+-])         # Either + or - in e.g. T-6, T+1
         (\s*\w+)       # Offset amount
         \s*            # Optional whitespace
         \]             # End ]
        ){0,1}          # End optional [offset] syntax
        (:[\w-]+){0,1}  # Optional type (e.g. :fail, :finish-all)
        $               # End
    """, re.X)
              
# Cylc's ISO 8601 format.
NODE_ISO_RE = re.compile(
    r"""^(\w+)       # Task name
        (?:\[        # Begin optional [offset] syntax
         (?!T[+-])   # Do not match a 'T-' or 'T+' (this is the old format)
         ([^\]]+)    # Continue until next ']'
         \]          # Stop at next ']'
        )?           # End optional [offset] syntax]
        (:[\w-]+|)$  # Optional type (e.g. :succeed)
     """, re.X)

# Cylc's ISO 8601 initial cycle time based format
NODE_ISO_ICT_RE = re.compile(
    r"""^(\w+)       # Task name
        \[\]         # Initial cycle time offset marker
        (?:\[        # Begin optional [offset] syntax
         ([^\]]+)    # Continue until next ']'
         \]          # Stop at next ']'
        )?           # End optional [offset] syntax]
        (:[\w-]+|)$  # Optional type (e.g. :succeed)
     """, re.X)

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

    def __init__( self, node, base_interval=None ):
        node_in = node
        # Get task name and properties from a graph node name.

        # Graph node name is task name optionally followed by:
        # - output label: foo:m1
        # - intercycle dependence: foo[T-6]
        # These may be combined: foo[T-6]:m1
        # Task may be defined at initial cycle time: foo[]
        # or relative to initial cycle time: foo[][+P1D]

        self.offset_is_from_ict = False
        self.is_absolute = False
        
        is_prev_cycling_format = False

        m = re.match( NODE_ISO_ICT_RE, node )
        if m:
            # node looks like foo[], foo[][-P4D], foo[]:fail, etc.
            self.is_absolute = True
            name, offset, outp = m.groups()
            self.offset_is_from_ict = True
            sign = ""
            prev_format = False
        else:
            m = re.match( NODE_ISO_RE, node )
            if m:
                # node looks like foo, foo:fail, foo[-PT6H], foo[-P4D]:fail...
                name, offset, outp = m.groups()
                sign = ""
                prev_format = False
            else:
                m = re.match( NODE_PREV_RE, node )
                if not m:
                    raise GraphNodeError( 'Illegal graph node: ' + node )
                is_prev_cycling_format = True
                # node looks like foo[T-6], foo[T-12]:fail...
                name, sign, offset, outp = m.groups()
                prev_format = True

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
            
        if self.offset_is_from_ict and not offset:
            offset = str(get_interval_cls().get_null())
        if offset:
            self.intercycle = True
            if prev_format:
                self.offset = base_interval.get_inferred_child(offset)
                if sign == "+":
                    self.offset = (-self.offset).standardise()
            else:
                self.offset = (-get_interval(offset)).standardise()
        else:
            self.intercycle = False
            self.offset = None
        if not flags.back_comp_cycling and is_prev_cycling_format:
            raise GraphNodeError(
                'Illegal graph offset (new-style cycling): ' + str(offset) +
                ' should be ' + str(self.offset)
            )


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


#!/usr/bin/env python

import re

class graphnode( object ):
    """A node in the cycle suite.rc dependency graph."""

    def __init__( self, node ):
        self.node_name = node
        # Get task name and properties from a graph node name.

        # Graph node name is task name optionally followed by:
        # - a conditional plotting indicator: foo*
        # - a special output indicator: foo:m1
        # - an intercycle dependency indicator: foo(T-6)
        # These may be combined: foo:m1(T-6)*

        # Defaults:
        self.intercycle = False
        self.special_output = False

        self.offset = None
        self.output = None

        # strip '*' indicators - only used for graphing
        # foo:m1(T-6)* -> foo:m1(T-6)
        node = re.sub( '\s*\*', '', node ) 

        # intercyle: foo:m1(T-6)
        m = re.match( '([\w:]+)\s*\(\s*T\s*([+-])\s*(\d+)\s*\)', node )
        if m:
            self.intercycle = True
            node, sign, offset = m.groups()
            self.intercycle_offset = offset
            if sign == '+':
                raise SuiteConfigError, self.node_name + ": only negative offsets allowed (e.g. T-6)"

        # special output: foo:m1
        m = re.match( '(\w+):(\w+)', node )
        if m:
            self.special_output = True
            node, output = m.groups()
            self.output = output

        # only name left now
        self.name = node

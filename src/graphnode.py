#!/usr/bin/env python

import re

class graphnode( object ):
    """A node in the cycle suite.rc dependency graph."""

    def __init__( self, node ):
        node_in = node
        # Get task name and properties from a graph node name.

        # Graph node name is task name optionally followed by:
        # - a conditional plotting indicator: foo*
        # - a special output indicator: foo:m1
        # - an intercycle dependency indicator: foo(T-6)
        # These may be combined: foo(T-6):m1*

        # Defaults:
        self.intercycle = False
        self.special_output = False

        self.offset = None
        self.output = None

        # strip '*' indicators - only used for graphing
        # foo(T-6):m1* -> foo(T-6):m1
        node = re.sub( '\s*\*', '', node ) 

        # parse and strip special output: foo(T-6):m1 -> foo(T-6)
        m = re.match( '(.*):(\w+)', node )
        if m:
            self.special_output = True
            node, self.output = m.groups()

        # parse and strip intercyle: foo(T-6) -> foo
        m = re.match( '([\w]+)\s*\(\s*T\s*([+-])\s*(\d+)\s*\)', node )
        if m:
            self.intercycle = True
            node, sign, self.offset = m.groups()
            if sign == '+':
                raise SuiteConfigError, node_in + ": only negative offsets allowed (e.g. T-6)"

        # only name left now
        self.name = node

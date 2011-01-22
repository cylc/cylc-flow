#!/usr/bin/env python

# import pygraphviz via this module, which tests if it is installed
# (as an external dependency, it may not be).

class GraphvizError( Exception ):
    """
    Attributes:
        message - what the problem is. 
        TO DO: element - config element causing the problem
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

try:
    import pygraphviz
except ImportError:
    raise GraphvizError, 'Cannot import pygraphviz.'

try:
    import xdot
except ImportError:
    raise GraphvizError, 'Cannot import xdot.'

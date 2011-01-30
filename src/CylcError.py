#!/usr/bin/env python

class CylcError( Exception ):
    """
    Attributes:
        message - what the problem is. 
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class TaskStateError( CylcError ):
    pass

class TaskNotFoundError( CylcError ):
    pass

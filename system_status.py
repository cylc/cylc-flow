#!/usr/bin/python

import Pyro.core

class system_status( Pyro.core.ObjBase ):

    def __init__( self ):
        Pyro.core.ObjBase.__init__(self)
        self.status = []

    def reset( self ):
        self.temp_status = []
    
    def report( self ):
        return self.status

    def update( self, str ):
        self.temp_status.append( str )

    def update_finished( self ):
        self.status = self.temp_status


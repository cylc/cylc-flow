#!/usr/bin/python

import Pyro.core
import logging
import sys

class main_switch( Pyro.core.ObjBase ):
    "class to take remote system control requests" 

    # the main program can take action on these when it is convenient.

    def __init__( self ):
        self.log = logging.getLogger( "main" )
        Pyro.core.ObjBase.__init__(self)
        self.system_halt = False
        self.system_pause = False

    def pause( self ):
        # call remotely via Pyro
        self.log.warning( "system pause requested" )
        self.system_pause = True

    def resume( self ):
        # call remotely via Pyro
        self.log.warning( "system resume requested" )
        self.system_pause = False 

    def shutdown( self ):
        # call remotely via Pyro
        self.log.warning( "system halt requested" )
        self.system_halt = True

#!/usr/bin/python

import Pyro.core
import logging
import sys

class control( Pyro.core.ObjBase ):

    def __init__( self, pyrod ):
        self.log = logging.getLogger( "main" )
        Pyro.core.ObjBase.__init__(self)
        self.system_halt = False
        self.system_pause = False
        self.pyro_daemon = pyrod

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
        self.log.warning( "system shutdown requested" )
        self.system_halt = True

    def clean_shutdown( self, message ):
        self.log.critical( 'System Halt: ' + message )
        self.pyro_daemon.shutdown( True ) 
        sys.exit(0)

#!/usr/bin/python

import Pyro.core
import logging

class dead_letter_box( Pyro.core.ObjBase ):
    # remote programs should attempt sending to this if they fail to
    # connect to their intended target objects.

    def __init__( self ):
        Pyro.core.ObjBase.__init__(self)
        self.log = logging.getLogger( "main" )

    def incoming( self, message ):
        self.log.warning( "DEAD LETTER: " + message )

#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import Pyro.core
import logging

class letter_box( Pyro.core.ObjBase ):
    # remote programs should attempt sending to this if they fail to
    # connect to their intended target objects.

    def __init__( self ):
        Pyro.core.ObjBase.__init__(self)
        self.log = logging.getLogger( "main" )

    def incoming( self, message ):
        self.log.warning( "DEAD LETTER: " + message )

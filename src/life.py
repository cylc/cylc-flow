#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# a Pyro object for miminal connection to check if a suite is running

import Pyro.core

class ping( Pyro.core.ObjBase ):
    def __init__( self, suite, owner ):
        self.owner = owner
        self.suite = suite
        Pyro.core.ObjBase.__init__( self )

    def identify( self ):
        return ( self.suite, self.owner )

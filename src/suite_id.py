#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

# A minimal Pyro-connected object to allow client programs to identify
# what suite is running at a given cylc port - by suite name and owner.

# All *other* suite objects should be connected to Pyro via qualified 
# names: owner.suite.object, to prevent accidental access to the wrong
# suite. This object, however, should be connected unqualified so that 
# that same ID method can be called on any active cylc port.

import Pyro.core

class identifier( Pyro.core.ObjBase ):
    def __init__( self, name, owner ):
        self.owner = owner
        self.name = name
        Pyro.core.ObjBase.__init__( self )

    def id( self ):
        return ( self.name, self.owner )

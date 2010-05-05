#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# always claim to have spawned already

class oneoff:
    def ready_to_spawn( self ):
        self.state.set_spawned()
        return False

    def has_spawned( self ):
        return True

#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


class sequential(object):
    # not "ready to spawn" unless 'finished'.
    def ready_to_spawn( self ):
        if self.state.is_finished() and not self.state.has_spawned():
            return True
        else:
            return False

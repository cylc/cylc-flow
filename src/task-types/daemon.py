#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


from task import task
from mod_oneoff import oneoff
import re

class daemon( oneoff, task ):
    # runs forever and adds outputs as messages matching a pattern come in

    def incoming( self, priority, message ):
        if re.match( self.output_pattern, message ):
            self.outputs.add( 10, message )

        task.incoming( self, priority, message )

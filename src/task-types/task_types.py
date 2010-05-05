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
from cycling_task import cycling_task
from asynchronous_task import asynchronous_task
from mod_pid import pid
from mod_oneoff import oneoff
from mod_nopid import nopid
import re

class forecast_model( pid, cycling_task ):
    # task class with previous instance dependence
    pass

class free_task( nopid, cycling_task ):
    # task class with no previous instance dependence
    pass

class daemon( oneoff, task ):
    # runs forever and adds outputs as messages matching a pattern come in

    def incoming( self, priority, message ):
        if re.match( self.output_pattern, message ):
            self.outputs.add( 10, message )

        task.incoming( self, priority, message )

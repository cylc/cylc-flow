#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


from task import task
from oneoff import oneoff
import re

class daemon( oneoff, task ):
    # A oneoff task that dynamically and adds outputs as messages
    # matching registered patterns come in. The corresponding real task
    # may keep running indefinitely, e.g. to watch for incoming
    # asynchronous data.

    # not 'daemon' - hasattr(task, 'daemon') returns True for all tasks 
    # due to the pyro daemon (I think).
    daemon_task = True  

    def incoming( self, priority, message ):
        # intercept incoming messages and check for a pattern match 
        for pattern in self.output_patterns:
            if re.match( pattern, message ):
                self.outputs.add( 10, message )

        task.incoming( self, priority, message )

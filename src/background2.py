#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# Like background, but announces itself before submitting the task.
# Used for simplest possible tests of using multiple job submit methods
# in one system.

import os
from job_submit import job_submit

class background2( job_submit ):

    def submit( self ):
        self.set_local_environment()
        print "Background2 job submit: " + self.task_name + "%" + self.cycle_time + " (" + self.task +")"
        self.execute_local( self.task )

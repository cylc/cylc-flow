#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import os
from job_submit import job_submit

class background( job_submit ):
# direct background execution 

    def submit( self ):
        self.set_local_environment()
        self.execute_local( self.task )

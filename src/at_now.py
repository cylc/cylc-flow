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

class at_now( job_submit ):
# submit a jobs using 'at -f FILE now'

    def submit( self ):
        self.set_local_environment()
        # 'at' requires file path, hence use of 'which' here:
        self.execute_local( 'at -f $(which ' + self.task + ') now' )

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
    # local background execution

    def construct_command( self ):
        log = self.task_id + '-$$.log'

        # Redirection of stdin is for remote background execution
        # (it allows ssh to exit immediately rather than wait for the
        # remote process to finish).

        self.command = self.jobfile_path + " </dev/null > " + log + " 2>&1 &" 

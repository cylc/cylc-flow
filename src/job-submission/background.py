#!/usr/bin/env python

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
    # This class overrides job submission command construction so that
    # the cylc task execution file will run in a background shell.

    def construct_command( self ):
        # Redirection of stdin here allows "background execution" of the
        # task even on a remote host (if one is specified in the taskdef
        # file) - ssh can exit immediately after invoking the job
        # script, without waiting for the remote process to finish.

        cwd = os.getcwd()
        out = cwd + '/' + self.task_id + '.out'
        err = cwd + '/' + self.task_id + '.err'
        self.command = self.jobfile_path + " </dev/null 1> " + out + " 2> " + err + " &" 
        self.logfiles.add_path( out )
        self.logfiles.add_path( err )

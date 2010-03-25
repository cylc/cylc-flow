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
import sys
from job_submit import job_submit

# invoke task on remote machine and exit immediately
# ssh normally waits for remote process to end, but we can avoid this by
# redirecting stdin to /dev/null, stdout to /dev/null or a JOB LOG FILE, 
# stderr to stdout, and backgrounding.

# NOTE: for multiple commands separated by ';'s, enclose in parentheses:
# ssh host '(echo one; echo two) </dev/null >/dev/null 2>&1 &'

class background_remote( job_submit ):

    def submit( self ):

        host = self.remote_host
        task = self.task

        remote_env = self.remote_environment_string()

        command = "( " + remote_env + "; " + task + " )"
        exe = command + " </dev/null >" + task + ".$$.log 2>&1 &" 

        #self.execute_local( [ 'ssh', host, "'" + exe + "'" ] )
        self.execute_local( 'ssh ' + host + " '" + exe + "'" )

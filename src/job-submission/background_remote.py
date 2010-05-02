#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import os, sys
import tempfile
from job_submit import job_submit

# Invoke the task on a remote machine and exit immediately:
# ssh host task < /dev/null > ID.$$.log &

# Ssh normally waits for the remote process to end, but we can avoid
# this by redirecting stdin to /dev/null, stdout to /dev/null or a JOB
# LOG FILE, stderr to stdout, and backgrounding.

# To invoke multiple commands separated by ';'s, enclose in parentheses:
# ssh host '(echo one; echo two) </dev/null >/dev/null 2>&1 &'

class background_remote( job_submit ):

    def copy_jobfile( self ):
        self.command = 'scp ' + self.jobfilename + ' ' + self.remote_host + ':'
        self.remote_jobfilename = '$HOME/' + os.path.basename( self.jobfilename )
        self.execute()   # execute the copy

    def construct_command( self ):
        if not self.remote_host:
            raise SystemExit( 'Remote host not defined for ' + self.task_id )
        self.copy_jobfile()
        exe = self.remote_jobfilename + " </dev/null >" + self.task_id + "-$$.log 2>&1 &" 
        self.command =  'ssh ' + self.remote_host + " '" + exe + "'" 

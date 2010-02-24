#!/usr/bin/python

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
        exe = command + " </dev/null >forecast.out 2>&1 &" 

        #self.execute_local( [ 'ssh', host, "'" + exe + "'" ] )
        self.execute_local( 'ssh ' + host + " '" + exe + "'" )

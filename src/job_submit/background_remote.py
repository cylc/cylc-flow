#!/usr/bin/python

import os
from job_submit import job_submit

# invoke task on remote machine and exit immediately
# ssh normally waits for remote process to end, but we can avoid this by
# redirecting stdin to /dev/null, stdout to /dev/null, stderr to stdout, 
# and backgrounding.

class background( job_submit ):

    host = 'oliverh-ws.greta'

    def construct_command( self ):
        # direct background execution 
        return 'ssh ' + host + ' + self.task + ' </dev/null >/dev/null 2>&1 &' 
        #return self.task

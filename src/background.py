#!/usr/bin/python

import os
from job_submit import job_submit

class background( job_submit ):
# direct background execution 

    def submit( self ):
        self.set_local_environment()
        self.execute_local( self.task )

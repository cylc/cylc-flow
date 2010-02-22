#!/usr/bin/python

import os
from job_submit import job_submit

class background( job_submit ):

    def construct_command( self ):
        # direct background execution 
        return self.task + ' &' 
        #return self.task

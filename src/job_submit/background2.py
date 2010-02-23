#!/usr/bin/python

# Like background, but announces itself before submitting the task.
# Used for simplest possible tests of using multiple job submit methods
# in one system.

import os
from job_submit import job_submit

class background2( job_submit ):

    def construct_command( self ):
        # direct background execution 
        return self.task + ' &' 

    def submit( self ):
        print "Background2 job submit: " + self.task
        job_submit.submit( self )

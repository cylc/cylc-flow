#!/usr/bin/python

import os
from job_submit import job_submit

class background_foo( job_submit ):

    def construct_command( self ):
        # direct background execution 
        return self.task + ' &' 

    def submit( self ):
        print "FOO: " + self.task
        job_submit.submit( self )

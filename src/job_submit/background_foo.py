#!/usr/bin/python

import os
from job_submit import job_submit

class background_foo( job_submit ):

    def construct_command( self ):
        # direct background execution 
        return self.task + ' &' 
        #return self.task

    def submit( self ):
        print "FOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO\n"
        job_submit.submit( self )

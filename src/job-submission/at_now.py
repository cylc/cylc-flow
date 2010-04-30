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
import tempfile
from job_submit import job_submit

class at_now( job_submit ):
    # submit a task using 'at -f FILE now'

    def submit( self ):
        jobfilename = tempfile.mktemp( prefix='cylc-') 
        jobfile = open( jobfilename, 'w' )
        self.write_job_env( jobfile )
        jobfile.write( self.task )
        jobfile.close() 

        self.execute( 'at -f ' + jobfilename + ' now' )

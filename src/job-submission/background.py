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
import stat
import tempfile
from job_submit import job_submit

class background( job_submit ):
    # direct background execution 

    def submit( self ):
        jobfilename = tempfile.mktemp( prefix='cylc-') 
        jobfile = open( jobfilename, 'w' )
        self.write_job_env( jobfile )
        jobfile.write( self.task )
        jobfile.close() 
        os.chmod( jobfilename, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

        self.execute( jobfilename )

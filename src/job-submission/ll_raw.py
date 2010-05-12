#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import shutil
import which
import fileinput
import os, re
import tempfile
from job_submit import job_submit

class ll_raw( job_submit ):

    def construct_jobfile( self ):
        self.method_description = 'by loadleveler, raw [llsubmit]'

        # create a new jobfile name
        self.jobfilename = self.get_jobfile_name()

        orig_file = which.which( self.task )  # full path needed if task file is in scripts dir
        shutil.copy( orig_file, self.jobfilename )

        self.compute_job_env()

        done = False
        for line in fileinput.input( self.jobfilename, inplace=True ):
            print line.strip()
            if not done and re.match( '^\s*#\s*@\s*queue\s*$', line ):
                print
                self.print_job_env()
                print
                done = True

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfilename

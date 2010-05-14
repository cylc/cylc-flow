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

        # check for multiple step loadleveler files
        queue_re = re.compile( '^\s*#\s*@\s*queue\s*$') 
        FILE = open( self.jobfilename, 'r' )
        lines = FILE.readlines()
        FILE.close()
        n_queue_directives = len( filter( queue_re.search, lines ) )

        done = False
        count = 0
        for line in fileinput.input( self.jobfilename, inplace=True ):
            print line.strip()
            if re.match( '^\s*#\s*@\s*queue\s*$', line ):
                count += 1
                if not done and count == n_queue_directives:
                    print
                    self.print_job_env()
                    print
                    done = True

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfilename

#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import which
import os, re
from job_submit import job_submit

class ll_raw( job_submit ):

    def write_jobfile( self, JOBFILE ):

        # get full path of task script (it could be defined relative
        # to system scripts dir in the taskdef file).
        orig_file = which.which( self.task )

        # read original and count '#@ queue' directives, in case is
        # a multiple step loadleveler job
        queue_re = re.compile( '^\s*#\s*@\s*queue\s*$') 
        FILE = open( orig_file, 'r' )
        lines = FILE.readlines()
        FILE.close()
        n_queue_directives = len( filter( queue_re.search, lines ) )

        # write original out to the jobfile line by line
        # inserting cylc environment etc. when we reach the final
        # queue directive.
        done = False
        count = 0
        for line in lines:
            line.strip()
            if re.match( '^\s*#\s*@\s*queue\s*$', line ):
                count += 1
                if not done and count == n_queue_directives:
                    self.write_environment( JOBFILE ) 
                    self.write_cylc_scripting( JOBFILE )
                    self.write_extra_scripting( JOBFILE )
                    done = True

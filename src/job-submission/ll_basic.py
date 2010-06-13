#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import os, re
import tempfile
from job_submit import job_submit

class ll_basic( job_submit ):
    # Submit a job to run via loadleveler (llsubmit)

    def __init__( self, task_id, ext_task, task_env, com_line, dirs, logs, owner, host ): 
        job_submit.__init__( self, task_id, ext_task, task_env, com_line, dirs, logs, owner, host ) 

        #out = self.running_dir + '/' + task_id + '.out'
        #err = self.running_dir + '/' + task_id + '.err'
        out = tempfile.mktemp( prefix = task_id + '-', dir= self.running_dir, suffix = ".out" ) 
        err = re.sub( '\.out$', '.err', out )
        self.logfiles.add_path( out )
        self.logfiles.add_path( err )

        # default directives
        directives = {}
        directives[ 'shell'    ] = '/bin/bash'
        directives[ 'job_name' ] = task_id
        directives[ 'output'   ] = out
        directives[ 'error'    ] = err
        # is initialdir required if output and error are full path?
        directives[ 'initialdir' ] = self.running_dir

        # add (or override with) taskdef directives
        for d in self.directives:
            directives[ d ] = self.directives[ d ]

        # now replace
        self.directives = directives

        self.directive_prefix = "# @ "
        self.final_directive  = "# @ queue"

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfile_path

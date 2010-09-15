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

    def __init__( self, task_id, ext_task, task_env, dirs, extra, logs, owner, host ): 
        # parent class init first
        job_submit.__init__( self, task_id, ext_task, task_env, dirs, extra, logs, owner, host ) 

        out = tempfile.mktemp( prefix = task_id + '-', dir= self.joblog_dir, suffix = ".out" ) 
        err = re.sub( '\.out$', '.err', out )
        self.logfiles.replace_path( '/.*/' + task_id + '-.*\.out', out )
        self.logfiles.replace_path( '/.*/' + task_id + '-.*\.err', err )

        # default directives
        directives = {}
        directives[ 'shell'    ] = '/bin/bash'
        #directives[ 'class'    ] = 'serial'
        directives[ 'class'    ] = 'test_linux'
        directives[ 'job_name' ] = task_id
        directives[ 'output'   ] = out
        directives[ 'error'    ] = err

        if self.homedir:
            # For local job submits self.homedir is defined
            # need to set initialdir directive, as we may be submitting
            # as a different user.
            directives[ 'initialdir' ] = self.homedir
            # For remote job submits we don't necessarily know the
            # remote homedir, but ssh automatically puts us there, so
            # don't need the directive.

        # add (or override with) taskdef directives
        for d in self.directives:
            directives[ d ] = self.directives[ d ]

        # now replace
        self.directives = directives

        self.directive_prefix = "# @ "
        self.final_directive  = "# @ queue"

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfile_path

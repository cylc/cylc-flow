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

    def __init__( self, task_id, ext_task, task_env, com_line, dirs, owner, host ): 
        job_submit.__init__( self, task_id, ext_task, task_env, com_line, dirs, owner, host ) 

        # default directives
        directives = {}
        directives[ 'shell'    ] = '/bin/bash'
        directives[ 'job_name' ] = task_id
        directives[ 'output'   ] = '$(job_name)-$(jobid).out'
        directives[ 'error'    ] = '$(job_name)-$(jobid).err'

        # add (or override with) taskdef directives
        for d in self.directives:
            directives[ d ] = self.directives[ d ]

        # now replace
        self.directives = directives

        self.directive_prefix = "# @ "
        self.final_directive  = "# @ queue"

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfile_path

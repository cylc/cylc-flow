#!/usr/bin/python

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

class loadleveler( job_submit ):
    # Submit a job to run via loadleveler (llsubmit)

    def configure( self, task_id, ext_task, env_vars, com_line, dirs, owner, host ): 
        job_submit.configure( self, task_id, ext_task, env_vars, com_line, dirs, owner, host ) 

        # default directives
        directives = {}
        directives[ 'shell'    ] = '/bin/bash'
        directives[ 'job_name' ] = task_id
        directives[ 'class'    ] = 'default'
        directives[ 'job_type' ] = 'serial'
        directives[ 'output'   ] = '$(job_name)-$(jobid).out'
        directives[ 'error'    ] = '$(job_name)-$(jobid).err'

        # add (or override with) taskdef directives
        for d in self.directives:
            directives[ d ] = self.directives[ d ]

        # now replace
        self.directives = directives

        self.method_description = 'by loadleveler, basic [llsubmit]'


    def construct_jobfile( self ):
        # create a new jobfile
        self.get_jobfile()

        # write loadleveler directives
        for d in self.directives.keys():
            self.jobfile.write( "#@ " + d + " = " + self.directives[ d ] + "\n" )

        # FINAL QUEUEING DIRECTIVE
        self.jobfile.write( "#@ queue\n\n" )

        # write cylc, system-wide, and task-specific environment vars 
        self.write_job_env()

        # write the task execution line
        self.jobfile.write( self.task + " " + self.commandline + "\n")
 
        # close the jobfile
        self.jobfile.close() 

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfilename

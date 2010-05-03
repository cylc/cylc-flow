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

    def construct_jobfile( self ):
        # create a new jobfile
        self.get_jobfile()

        # write loadleveler directives
        # $(jobid) is the numerical suffix of the job name shown by llq
        
        self.jobfile.write( "#@ shell        = /bin/bash\n" )
        self.jobfile.write( "#@ job_name     = " + self.task_id + "\n" )
        self.jobfile.write( "#@ class        = default \n" )
        self.jobfile.write( "#@ job_type     = serial\n" )
        self.jobfile.write( "#@ output       = $(job_name)-$(jobid).out\n" )
        self.jobfile.write( "#@ error        = $(job_name)-$(jobid).err\n" )

        # OVERRIDE WITH TASKDEF DIRECTIVES HERE

        # FINAL QUEUEING DIRECTIVE
        self.jobfile.write( "#@ queue\n\n" )

        # FOR EXTRA SCRIPTING BEFORE TASK SCRIPT OVERRIDE
        # WRITE_JOB_ENV() AND THEN CALL PARENT METHOD.
        # write cylc, system-wide, and task-specific environment vars 
        self.write_job_env()

        # write the task execution line
        self.jobfile.write( self.task )
        # close the jobfile
        self.jobfile.close() 

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfilename

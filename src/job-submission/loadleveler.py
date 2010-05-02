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

    def write_job_directives( self, jobfile ):
        # write loadleveler directives
        # $(jobid) is the numerical suffix of the job name shown by llq
        jobfile.write( "#@ job_name     = " + self.task_name + "_" + self.cycle_time + "\n" )
        jobfile.write( "#@ class        = default \n" )
        jobfile.write( "#@ job_type     = serial\n" )
        jobfile.write( "#@ output       = $(job_name)-$(jobid).out\n" )
        jobfile.write( "#@ error        = $(job_name)-$(jobid).err\n" )
        jobfile.write( "#@ queue\n\n" )

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfilename

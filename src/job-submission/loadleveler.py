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

    # submit a job to run via loadleveler (llsubmit)
    #   [sudo -u OWNER] llsubmit FILE 

    # If OWNER is supplied in the taskdef, /etc/sudoers must be # configured to allow the cylc operator to run llsubmit as the task
    # owner. FILE is a temporary file created to contain loadleveler
    # directives and set the execution environment before running the
    # task (getting environment variables past 'sudo' and llsubmit is
    # otherwise problematic).

    def __init__( self, task_id, ext_task, config, extra_vars, owner, host ):

        # adjust the task owner's username according to which system are
        # we running on (devel, test, oper).

        cylc_user = os.environ['USER']
        cylc_home = os.environ['HOME']
        system = re.sub( '^.*_', '', cylc_user )  

        # adjust task owner for the system
        if not owner:
            raise SystemExit( "No owner for EcoConnect task " + self.task_name )

        if re.match( '^.*_oper', owner ):
            # strip off the system suffix
            owner = re.sub( '_oper$', '', owner )

        # append the correct system suffix
        owner += '_' + system

        loadleveler.__init__( self, task_id, ext_task, config, extra_vars, owner, host )


    def write_directives( self, jobfile ):
        # write loadleveler directives
        jobfile.write( "#@ job_name     = " + self.task_name + "_" + self.cycle_time + "\n" )
        jobfile.write( "#@ class        = default \n" )
        jobfile.write( "#@ job_type     = serial\n" )
        jobfile.write( "#@ output       = " + self.task_name + "_" + self.cycle_time + ".out\n" )
        jobfile.write( "#@ error        = " + self.task_name + "_" + self.cycle_time + ".err\n" )
        jobfile.write( "#@ queue\n\n" )

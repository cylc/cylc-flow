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
from loadleveler import loadleveler

class loadleveler_ecoconnect( loadleveler ):

    def __init__( self, task_id, ext_task, config, extra_vars, owner, host ):
        # adjust task owner's username for devel, test, or oper.
        cylc_user = os.environ['USER']
        self.system = re.sub( '^.*_', '', cylc_user )  

        self.cylc_home = os.environ['HOME']

        if not owner:
            raise SystemExit( "No owner for EcoConnect task " + task_id )

        if re.match( '^.*_oper', owner ):
            # strip off the system suffix
            owner = re.sub( '_oper$', '', owner )
        # append the correct system suffix
        owner += '_' + self.system

        loadleveler.__init__( self, task_id, ext_task, config, extra_vars, owner, host )

    def write_job_directives( self ):
        # ecoconnect loadleveler directives
        self.jobfile.write( "#@ job_name     = " + self.task_id + "\n" )
        #self.jobfile.write( "#@ class        = " + self.system + "\n" )     # WHEN PROPER CLASSES CONFIGURED!
        self.jobfile.write( "#@ class        = test_linux \n" )  # TEMPORARY fc-test ONLY CLASS
        self.jobfile.write( "#@ job_type     = serial\n" )
        self.jobfile.write( "#@ initialdir  = /" + self.system + "/ecoconnect/" + self.owner + "\n" )
        self.jobfile.write( "#@ output       = $(job_name)-$(jobid).out\n" )
        self.jobfile.write( "#@ error        = $(job_name)-$(jobid).err\n" )
        self.jobfile.write( "#@ shell        = /bin/bash\n" )
        self.jobfile.write( "#@ queue\n\n" )

    def write_extra_env( self ):
        self.jobfile.write( ". " + self.cylc_home + "/bin/ecfunctions.sh\n\n" )

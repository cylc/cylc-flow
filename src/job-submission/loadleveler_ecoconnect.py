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

    def configure( self, task_id, ext_task, env_vars, com_line, dirs, owner, host ): 
        loadleveler.configure( self, task_id, ext_task, env_vars, com_line, dirs, owner, host ) 

        # adjust task owner's username for devel, test, or oper.
        cylc_user = os.environ['USER']
        system = re.sub( '^.*_', '', cylc_user )  
        self.cylc_home = os.environ['HOME']

        if not self.owner:
            raise SystemExit( "No owner for EcoConnect task " + task_id )

        if re.match( '^.*_oper', self.owner ):
            # strip off the system suffix
            self.owner = re.sub( '_oper$', '', self.owner )
        # append the correct system suffix
        self.owner += '_' + system

        # ecoconnect-specific loadleveler directives
        # CHANGE ONCE PROPER LOADLEVELER QUEUES ARE CONFIGURED
        #!!!! self.directives[ 'class'    ] = self.system
        self.directives[ 'class'       ] = 'test_linux'
        # and initialdir, as owner has changed above
        self.directives[ 'initialdir' ] = '~' + self.owner

        self.method_description = 'by loadleveler, EcoConnect [llsubmit]'

    def write_job_env( self ):
        loadleveler.write_job_env( self )
        self.jobfile.write( ". " + self.cylc_home + "/bin/ecfunctions.sh\n\n" )

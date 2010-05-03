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

    def __init__( self, task_id, ext_task, config, extra_vars, extra_directives, owner, host ):
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

        directives = {}
        #!!!! directives[ 'class'    ] = self.system # !!!!
        directives[ 'class'       ] = 'test_linux'
        #!!!! directives[ 'initial_dir' ] = "/" + self.system + "/ecoconnect/" + self.owner  + "/running"

        # add (or override with) taskdef directives
        for d in extra_directives.keys():
            directives[ d ] = extra_directives[ d ]

        loadleveler.__init__( self, task_id, ext_task, config, extra_vars, directives, owner, host )
        self.method_description = 'by [llsubmit] (ecoconnect method)'

    def write_job_env( self ):
        loadleveler.write_job_env( self )
        self.jobfile.write( ". " + self.cylc_home + "/bin/ecfunctions.sh\n\n" )

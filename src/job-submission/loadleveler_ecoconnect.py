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

    def __init__( self, dummy_mode, global_env ):
        # check we are running in an ecoconnect system
        # cylc should be running as ecoconnect_(devel|test|oper)

        cylc_owner = os.environ[ 'USER' ]

        m = re.match( '^(.*)_(devel|test|oper)$', cylc_owner )
        if m:
            (junk, ecoc_system ) = m.groups()
        else:
            raise SystemExit( "Cylc is not running in an EcoConnect environment" )

        self.ecoc_system = ecoc_system
        self.ecoc_system_bin = os.environ[ 'HOME' ] + '/bin'

        loadleveler.__init__( self, dummy_mode, global_env ) 


    def configure( self, task_id, ext_task, env_vars, com_line, dirs, owner, host ): 
        if not owner:
            raise SystemExit( "EcoConnect tasks require an owner: " + task_id )

        # transform owner username for devel, test, or oper systems

        # strip off any existing system suffix defined in the taskdef file
        m = re.match( '^(.*)_(devel|test|oper)$', owner )
        if m:
            ( owner_name, junk ) = m.groups()
        else:
            owner_name = owner

        # append the correct system suffix
        owner = owner_name + '_' + self.ecoc_system

        loadleveler.configure( self, task_id, ext_task, env_vars, com_line, dirs, owner, host ) 

        # ecoconnect-specific loadleveler directives
        # CHANGE ONCE PROPER LOADLEVELER QUEUES ARE CONFIGURED
        #!!!! self.directives[ 'class'    ] = self.system !!!!
        self.directives[ 'class'       ] = 'test_linux'

        self.method_description = 'by loadleveler, EcoConnect [llsubmit]'

    def write_job_env( self ):
        loadleveler.write_job_env( self )
        self.jobfile.write( ". " + self.ecoc_system_bin + "/ecfunctions.sh\n\n" )

    def execute_command( self ):
        print " > submitting task (via " + self.jobfilename + ") " + self.method_description
        # run as owner, in owner's $HOME/running directory
        if self.owner != os.environ['USER']:
            self.command = 'cd ~owner/running; sudo -u ' + self.owner + ' ' + self.command

        # execute local command to submit the job
        os.system( self.command )

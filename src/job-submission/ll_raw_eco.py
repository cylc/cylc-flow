#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import shutil
import fileinput
import os, re
import tempfile
from ll_raw import ll_raw

class ll_raw_eco( ll_raw ):

    def __init__( self, task_id, ext_task, env_vars, com_line, dirs, owner, host ): 
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

        ll_raw.__init__( self, task_id, ext_task, env_vars, com_line, dirs, owner, host ) 

        self.method_description = 'by loadleveler, EcoConnect raw [llsubmit]'

    def construct_command( self ):
        self.method_description = 'by loadleveler, raw, ecoconnect [llsubmit]'
        self.command = 'llsubmit ' + self.jobfilename

    def execute_command( self ):
        print " > submitting task (via " + self.jobfilename + ") " + self.method_description
        # run as owner, in owner's $HOME/running directory
        if self.owner != os.environ['USER']:
            self.command = 'cd ~' + self.owner + '/running; sudo -u ' + self.owner + ' ' + self.command

        # execute local command to submit the job
        os.system( self.command )

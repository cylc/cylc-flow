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
from ll_basic import ll_basic

class ll_basic_eco( ll_basic ):

    def set_running_dir( self ):
        # ~owner/running
        self.running_dir = self.homedir + '/running'

    def set_owner_and_homedir( self, owner = None ):
        # cylc should be running as ecoconnect_(devel|test|oper)
        if not owner:
            raise SystemExit( "EcoConnect tasks require an owner: " + task_id )

        m = re.match( '^(.*)_(devel|test|oper)$', self.cylc_owner )
        if m:
            (junk, ecoc_system ) = m.groups()
        else:
            raise SystemExit( "Cylc is not running in an EcoConnect environment" )

        # transform owner username for devel, test, or oper systems
        # strip off any existing system suffix defined in the taskdef file
        m = re.match( '^(.*)_(devel|test|oper)$', owner )
        if m:
            ( owner_name, junk ) = m.groups()
        else:
            owner_name = owner

        # append the correct system suffix
        owner = owner_name + '_' + ecoc_system

        ll_basic.set_owner_and_homedir( self, owner )


    def __init__( self, task_id, ext_task, task_env, com_line, dirs, extra, logs, owner, host ): 

        if 'class' not in dirs:
            # DEFAULT ECOCONNECT LOADLEVELER DIRECTIVES
            # dirs[ 'class'    ] = self.system !!!! TO DO: WHEN FINAL LL CLASSES CONFIGURED
            dirs[ 'class' ] = 'test_linux'

        ll_basic.__init__( self, task_id, ext_task, task_env, com_line, dirs, extra, logs, owner, host ) 


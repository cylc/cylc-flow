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
from ll_basic import ll_basic

class ll_basic_eco( ll_basic ):

    def __init__( self, task_id, ext_task, task_env, com_line, dirs, owner, host ): 
        # check we are running in an ecoconnect system
        # cylc should be running as ecoconnect_(devel|test|oper)

        cylc_owner = os.environ[ 'USER' ]

        m = re.match( '^(.*)_(devel|test|oper)$', cylc_owner )
        if m:
            (junk, ecoc_system ) = m.groups()
        else:
            raise SystemExit( "Cylc is not running in an EcoConnect environment" )

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
        owner = owner_name + '_' + ecoc_system

        ll_basic.__init__( self, task_id, ext_task, task_env, com_line, dirs, owner, host ) 

        # override running dir to ~owner/running
        self.running_dir = '/' + ecoc_system + '/ecoconnect/' + owner + '/running'

        # ecoconnect-specific loadleveler directives
        # CHANGE ONCE PROPER LOADLEVELER QUEUES ARE CONFIGURED
        #!!!! self.directives[ 'class'    ] = self.system !!!!
        self.directives[ 'class' ] = 'test_linux'

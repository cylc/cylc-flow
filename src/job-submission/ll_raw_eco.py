#!/usr/bin/env python


import os, re
from ll_raw import ll_raw

class ll_raw_eco( ll_raw ):

    def __init__( self, task_id, ext_task, task_env, dirs, pre_scr, post_scr, owner, host ): 

        # all ecoconnect tasks must be explicitly owned
        if not owner:
            raise SystemExit( "EcoConnect tasks require an owner: " + task_id )

        # cylc should be running as ecoconnect_(devel|test|oper)
        suite_owner = os.environ['USER']
        m = re.match( '^(.*)_(devel|test|oper)$', suite_owner )
        if m:
            (junk, ecoc_sys ) = m.groups()
        else:
            raise SystemExit( "This suite is not running in an EcoConnect environment" )

        # transform owner username for devel, test, or oper suites
        # strip off any existing suite suffix defined in the taskdef file
        m = re.match( '^(.*)_(devel|test|oper)$', owner )
        if m:
            ( owner_name, junk ) = m.groups()
        else:
            owner_name = owner

        # append the correct suite suffix
        owner = owner_name + '_' + ecoc_sys

        ll_raw.__init__( self, task_id, ext_task, task_env, dirs, pre_scr, post_scr, owner, host ) 

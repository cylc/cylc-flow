#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# job submission (external task execution) base class

# specific submission methods should be formulated as derived classes in
# the job_submit sub-directory of the main cylc installation or of the
# task definition directories for specific cylc systems.

import re, os, sys
import subprocess
import cycle_time

class job_submit:

    def __init__( self, task_id, ext_task, config, extra_vars, owner, host ):

        self.task = ext_task
        self.remote_host = host
        self.owner = owner
        self.config = config

        self.task_id = task_id
        self.extra_vars = extra_vars

        # extract cycle time
        self.cycle_time = None
        try:
            ( self.task_name, tag ) = task_id.split( '%' )
        except ValueError:
            self.task_name = task_id
        else:
            if cycle_time.is_valid( tag ):
                self.cycle_time = tag
                self.tag = None 
            else:
                self.cycle_time = None
                self.tag = tag

    def interpolate( self, string ):

        # $VARNAME
        m = re.findall( "\$([a-zA-Z0-9_]+)", string )
        for var in m:
            if var in os.environ:
                # replace value with the env value
                val = os.environ[ var ]
                string = re.sub( '\$' + var, val, string )

        # ${VARNAME}
        m = re.findall( "\$\{([a-zA-Z0-9_]+)\}", string )
        for var in m:
            if var in os.environ:
                # replace value with the env value
                val = os.environ[ var ]
                string = re.sub( '\$\{' + var + '\}', val, string )

        return string

    def write_job_env( self, file ):

        file.write("export TASK_ID=" + self.task_id + "\n" )
        file.write("export CYCLE_TIME=" + self.cycle_time + "\n" )
        file.write("export TASK_NAME=" + self.task_name + "\n" )
        file.write("export CYLC_DIR=" + os.environ[ 'CYLC_DIR' ] + "\n" )
        file.write(". $CYLC_DIR/cylc-env.sh\n")
        file.write("export PATH=" + os.environ['PATH'] + "\n" )  # for system scripts dir

        # global variables
        if 'CYLC_ON' in os.environ.keys():
            file.write("export CYLC_ON=true\n" )
        file.write("export CYLC_NS_GROUP=" + os.environ[ 'CYLC_NS_GROUP' ] + "\n" )
        file.write("export CYLC_NS_HOST=" + os.environ[ 'CYLC_NS_HOST' ] + "\n" )

        # system-specific global variables
        env = self.config.get('environment')
        for VAR in env.keys():
            file.write("export " + VAR + "=" + str( env[VAR] ) + "\n" )

        # extra task-specific variables
        for entry in self.extra_vars:
            [ var_name, value ] = entry
            value = self.interpolate( value )
            file.write("export " + var_name + "=" + value + "\n" )

    def submit( self ):
        raise SystemExit( "job_submit base class submit must be overridden")

    def execute( self, command ):
        if self.owner:
            if self.owner != os.environ['USER']:
                command = 'sudo -u ' + self.owner + ' ' + command
        os.system( command + ' &' )

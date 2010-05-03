#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# Job submission (external task execution) base class

# Classes derived from this will submit jobs as (or similar):
#  [sudo -u OWNER] {command} FILE 
 
# Derived submission methods must be added to the job_submit.py
# module in system definition directories to be available for use
# (and add to the default list in _cylc-configure too).

# If OWNER is supplied (via the taskdef file) /etc/sudoers must be
# configured to allow the cylc operator to run {command} as owner FILE
# is a temporary file that created and submitted to run the task. It
# should contain all cylc, system-wide, and task-specific environment
# variables, batch queue scheduler directives (e.g. for qsub or
# loadleveler directives), etc. (Setting up the correct execution 
# environment, through 'sudo' and {command} is very difficult if we try
# to submit the actual task script directory).

import re, os, sys
import subprocess
import tempfile, stat
import cycle_time

class job_submit:

    def __init__( self, task_id, ext_task, config, extra_vars, owner, host ):

        self.task = ext_task
        self.owner = owner
        self.config = config

        if host:
            # DOCUMENT THIS: CAN USE ENVIRONMENT VARS IN HOST NAME!
            self.remote_host = self.interpolate( host )

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

    def write_job_env( self ):
        self.jobfile.write("export TASK_ID=" + self.task_id + "\n" )
        self.jobfile.write("export CYCLE_TIME=" + self.cycle_time + "\n" )
        self.jobfile.write("export TASK_NAME=" + self.task_name + "\n" )
        self.jobfile.write("export CYLC_DIR=" + os.environ[ 'CYLC_DIR' ] + "\n" )
        self.jobfile.write(". $CYLC_DIR/cylc-env.sh\n")
        self.jobfile.write("export PATH=" + os.environ['PATH'] + "\n" )  # for system scripts dir

        # global variables
        if 'CYLC_ON' in os.environ.keys():
            self.jobfile.write("export CYLC_ON=true\n" )
        self.jobfile.write("export CYLC_NS_GROUP=" + os.environ[ 'CYLC_NS_GROUP' ] + "\n" )
        self.jobfile.write("export CYLC_NS_HOST=" + os.environ[ 'CYLC_NS_HOST' ] + "\n" )

        # system-specific global variables
        env = self.config.get('environment')
        for VAR in env.keys():
            self.jobfile.write("export " + VAR + "=" + str( env[VAR] ) + "\n" )

        # extra task-specific variables
        for VAR in self.extra_vars.keys():
            value = self.interpolate( self.extra_vars[ VAR ] )
            self.jobfile.write("export " + VAR + "=" + str( value )+ "\n" )

    def get_jobfile( self ):
        # get a new temp filename
        self.jobfilename = tempfile.mktemp( prefix='cylc-') 
        # open the file
        self.jobfile = open( self.jobfilename, 'w' )

    def construct_command( self ):
        raise SystemExit( "Job Submit base class: OVERRIDE ME" )

    def construct_jobfile( self ):
        # create a new jobfile
        self.get_jobfile()
        # write cylc, system-wide, and task-specific environment vars 
        self.write_job_env()
        # write the task execution line
        self.jobfile.write( self.task )
        # close the jobfile
        self.jobfile.close() 

    def submit( self ):
        # THIS IS CALLED TO SUBMIT A TASK
        # construct a jobfile to run the task
        self.construct_jobfile()
        # construct a command to submit the jobfile
        self.construct_command()
        # execute the constructed command
        self.execute_command()

    def delete_jobfile( self ):
        # called by task class when the job finishes
        os.unlink( self.jobfilename )

    def execute_command( self ):
        # set the jobfile executable
        os.chmod( self.jobfilename, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )
        # ran as owner, if necessary
        if self.owner:
            if self.owner != os.environ['USER']:
                self.command = 'sudo -u ' + self.owner + ' ' + self.command
        # execute local command to submit the job
        os.system( self.command )

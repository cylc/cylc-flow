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

    def __init__( self, dummy_mode, global_env ):
        self.dummy_mode = dummy_mode
        self.global_env = global_env
        self.method_description = 'Job Submit base class: OVERRIDE ME'


    def configure( self, task_id, ext_task, params, owner, host ): 

        if self.dummy_mode:
            self.task = "_cylc-dummy-task"
        else:
            self.task = ext_task

        self.owner = owner

        if host:
            # DOCUMENT THIS: CAN USE ENVIRONMENT VARS IN HOST NAME!
            self.remote_host = self.interpolate( host )

        self.task_id = task_id
        self.extra_vars  = params[ 'env' ]
        self.directives  = params[ 'dir' ]
        self.commandline = params[ 'com' ]

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

        # task-specific environment variables
        self.task_env = {}
        self.task_env[ 'TASK_ID'    ] = self.task_id
        self.task_env[ 'CYCLE_TIME' ] = self.cycle_time
        self.task_env[ 'TASK_NAME'  ] = self.task_name

    def interpolate_local_env( self, string ):
        interp_string = string
        for var in re.findall( "\$\{{0,1}([a-zA-Z0-9_]+)\}{0,1}", interp_string ):
            if var in os.environ:
                # replace value with the env value
                val = os.environ[ var ]
                interp_string = re.sub( '\$\{{0,1}' + var + '\}{0,1}', val, interp_string )

        # replace '@' with '$' (env vars to evaluate at execution time)
        # CURRENT LIMITATION: NO '@'S ALLOWED EXCEPT FOR THIS PURPOSE
        interp_string = re.sub( '@', '$', interp_string )

        return interp_string


    def interpolate( self, env ):
        # Interpolate any variables in env values: $VARNAME or ${VARNAME}.
        # First self-interpolate (if one variable refers to another).
        # Second interpolate any remaining variables from the local
        # environment (this also gets self-referals that contain
        # environment variables).

        interpolated_env = {}

        for variable in env:
            value = env[ variable ]

            # 1. self-interpolation
            for var in re.findall( "\$\{{0,1}([a-zA-Z0-9_]+)\}{0,1}", value ):
                if var in env:
                    val = env[ var ]
                    value = re.sub( '\$\{{0,1}' + var + '\}{0,1}', val, value )

            # 2. local environment interpolation
            for var in re.findall( "\$\{{0,1}([a-zA-Z0-9_]+)\}{0,1}", value ):
                if var in os.environ:
                    # replace value with the env value
                    val = os.environ[ var ]
                    value = re.sub( '\$\{{0,1}' + var + '\}{0,1}', val, value )

            # 3. replace '@' with '$' (env vars to evaluate at execution time)
            # CURRENT LIMITATION: NO '@'S ALLOWED EXCEPT FOR THIS PURPOSE
            value = re.sub( '@', '$', value )

            interpolated_env[ variable ] = value

        return interpolated_env

    def write_job_env( self ):
        # combine environment dicts:
        big_env = {}
        
        # global environment variables
        for var in self.global_env:
            big_env[ var ] = str( self.global_env[ var] )

        # general task specific variables
        env = self.task_env
        for var in env:
            big_env[ var ] = str( env[ var] )

        # special task specific variables, from taskdef
        env = self.extra_vars
        for var in env:
            big_env[ var ] = str( env[ var ] )

        # interpolate (self and environment)
        # e.g. task-specific (taskdef) vars that use global
        # (system_config) vars or pre-existing environment vars:
        final_env = self.interpolate( big_env )

        # now write the lot to the jobfile
        for var in final_env:
            self.jobfile.write( "export " + var + "=\"" + final_env[var] + "\"\n" )

        # ACCESS TO CYLC (for 'cylc message'), AND TO SUB-SCRIPTS
        # RESIDING IN THE SYSTEM DIRECTORY, BY SPAWNED TASKS IS BY
        # SOURCING:
        # . $CYLC_DIR/cylc-env.sh
        # IN THE JOBFILE (see src/job_submission/job_submit.py)

        # REMOTE TASKS MUST DEFINE (the remote) CYLC_DIR and
        # CYLC_SYSTEM_DIR in the taskdef file %ENVIRONMENT key
        # (full path with no interpolation).  The new (remote) values
        # will will replace the original (local) values in big_env
        # above (then full path to remote task script not required - if
        # in the remote $CYLC_SYSTEM_DIR/scripts).

        self.jobfile.write(". $CYLC_DIR/cylc-env.sh\n")

        # self.jobfile.write("export PATH=" + os.environ['PATH'] + "\n" )  # for system scripts dir

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

        # interpolate env vars in the commandline
        # don't need to interpolate local task-specific vars as these
        # will be defined explicitly above the commandline itself.
        commandline = ' '.join( self.commandline ) 
        commandline = self.interpolate_local_env( commandline )

        # write the task execution line
        self.jobfile.write( self.task + " " + commandline + "\n")
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
        print ' - deleting jobfile ' + self.jobfilename
        os.unlink( self.jobfilename )

    def execute_command( self ):
        # set the jobfile executable
        print " > submitting task (via " + self.jobfilename + ") " + self.method_description
        os.chmod( self.jobfilename, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )
        # ran as owner, if necessary
        if self.owner:
            if self.owner != os.environ['USER']:
                self.command = 'sudo -u ' + self.owner + ' ' + self.command
        # execute local command to submit the job
        os.system( self.command )

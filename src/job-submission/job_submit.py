#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

# TO DO: UPDATE, MOVE, OR DELETE THIS DOCUMENTATION:
        # REMOTE TASKS MUST DEFINE (the remote) CYLC_DIR and
        # CYLC_SYSTEM_DIR in the taskdef file %ENVIRONMENT key
        # (full path with no interpolation).  The new (remote) values
        # will will replace the original (local) values in big_env
        # above (then full path to remote task script not required - if
        # in the remote $CYLC_SYSTEM_DIR/scripts).


# Job submission (external task execution) base class. Derived classes
# must be added to job_submit_methods.py

# Writes a temporary "job file" that sets the execution environment for 
# access to cylc as well as task-specific environment variables defined
# in the taskdef file before executing the task task script proper.

# Derived job submission classes specify the means by which the job
# file itself is executed. E.g. simplest case, local background
# execution with no IO redirection or log file: 'FILE &'

# If OWNER is defined and REMOTE_HOST is not, submit locally by:
#  sudo -u OWNER submit(FILE) 
 
# If REMOTE_HOST is defined and OWNER is not, the job file is submitted
# by copying it to the remote host with scp, and executing the defined
# submit(FILE) on the remote host by ssh. Passwordless ssh to the remote
# host must be configured. 

# If REMOTE_HOST and OWNER are defined, we scp and ssh to
# 'OWNER@REMOTE_HOST', thus passwordless ssh to remote host as OWNER
# must be configured.

import re, os, sys
import subprocess
import tempfile, stat
import cycle_time
from interp_env import interp_self, interp_other, interp_local, interp_local_str, replace_delayed, interp_other_str, replace_delayed_str

class job_submit:

    # class variables to be set by the task manager
    dummy_mode = False
    global_env = {}

    def __init__( self, task_id, ext_task, task_env, com_line, dirs, owner, host ): 

        # unique task identity
        self.task_id = task_id

        # task owner
        self.owner = owner

        # in dummy mode, replace the real external task with the dummy task
        self.task = ext_task
        if job_submit.dummy_mode:
            self.task = "_cylc-dummy-task"

        # extract cycle time (cylcing tasks) or tag (asynchronous tasks)
        # from the task id: NAME%CYCLE_TIME or NAME%TAG.
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

        # The values of task-specific environment variables defined in
        # the taskdef file may reference other environment variables:
        # (i) other task-specific environment variables $FOO, ${FOO}
        # (ii) global cylc environment variables $FOO, ${FOO}
        # (iii) local environment variables $FOO, ${FOO}
        # (iv) "delayed local" environment varables $[BAR] that should
        #      not be evaluated until the task executes (potentially on
        #      a remote platform under another username).

        # So, for each task-specific environment variable VALUE:
        #  * interpolate any references to other task-specific variables
        #    (otherwise we have to arrange for the variables to be
        #    exported in the right order so that all variables are
        #    defined before they are used).
        #  * then interpolate any references to cylc global variables
        #    (this is usually not necessary if we export globals before
        #    task-specifics, but doing so allows users to override local
        #    environment variables in the system_config file ... which
        #    may be useful).
        #  * then interpolate any remaining variables from the local env
        #    (leaving them as literal '$FOO' could be a mistake for 
        #    tasks that are submitted on remote machines; that's what
        #    cylc's $[FOO] is for).
        #  * then replace delayed variables $[FOO] with literal '$FOO'

        # Note that global env already has self-, environment- variable
        # references worked out in config init (but not delayed
        # variables, as user may define global delayed vars that are
        # then referred to in task-specific vars!) .

        # Add the variables that all tasks must have
        # (doing this *before* interpolating, below, means that any
        # reference to '$CYCLE_TIME' in the taskdef file will be 
        # interpolated to the value of self.cycle time and NOT to
        # any $CYCLE_TIME that happens to be in the user's environment
        # prior to running the scheduler or run-task!
        task_env[ 'TASK_ID'    ] = self.task_id
        task_env[ 'CYCLE_TIME' ] = self.cycle_time
        task_env[ 'TASK_NAME'  ] = self.task_name

        task_env = interp_self( task_env )
        task_env = interp_other( task_env, job_submit.global_env )
        task_env = interp_local( task_env )
        task_env = replace_delayed( task_env )
        self.global_env = replace_delayed( job_submit.global_env )

        self.task_env = task_env

        # same for the task script command line
        commandline = ' '.join( com_line ) 
        commandline = interp_other_str( commandline, self.task_env )
        commandline = interp_other_str( commandline, job_submit.global_env )
        commandline = interp_local_str( commandline )
        commandline = replace_delayed_str( commandline )

        self.commandline = commandline

        # queueing system directives
        self.directives  = dirs
        
        # directive prefix, e.g. '#QSUB ' (qsub), or '#@ ' (loadleveler)
        # OVERRIDE IN DERIVED CLASSES
        self.directive_prefix = "# DIRECTIVE-PREFIX "

        # final directive, WITH PREFIX, e.g. '#@ queue' for loadleveler
        self.final_directive = ""
        
        # a remote host can be defined by environment variables
        if host:
            host = interp_other_str( host, job_submit.global_env )
            host = interp_other_str( host, self.task_env )
            host = interp_local_str( host )
            self.remote_host = host
        else:
            self.remote_host = None

        # by default, run in cylc user's home directory ...
        self.running_dir = '$HOME'
        # ... because '~' not recognized by os.chdir().
        #if self.owner:
        #    self.running_dir = '~' + self.owner

        self.remote_jobfile_path = None # default required in cleanup()

    def submit( self, dry_run ):
        # CALL THIS TO SUBMIT THE TASK

        # get a new temp filename
        self.jobfile_path = tempfile.mktemp( prefix='cylc-') 
        
        # open the job file to write
        JOBFILE = open( self.jobfile_path, 'w' )

        # write the job file
        self.write_jobfile( JOBFILE )

        # close the jobfile
        JOBFILE.close() 

        # submit the file
        if self.remote_host and not self.dummy_mode:
            return self.submit_jobfile_remote( dry_run )
        else:
            return self.submit_jobfile_local( dry_run )

    def write_jobfile( self, FILE ):
        FILE.write( '#!/bin/bash\n' )
        self.write_directives( FILE )
        self.write_environment( FILE )
        self.write_cylc_scripting( FILE )
        self.write_extra_scripting( FILE )
        self.write_task_execute( FILE ) 
        FILE.write( '#EOF' )

    def write_directives( self, FILE ):
        if len( self.directives.keys() ) == 0:
            return
        for d in self.directives:
            FILE.write( self.directive_prefix + d + " = " + self.directives[ d ] + "\n" )
        FILE.write( self.final_directive + "\n" )

    def write_environment( self, FILE ):
        # write the environment scripting to the jobfile

        #for env in [ job_submit.global_env, self.task_env ]:

        FILE.write( "\n# TASK EXECUTION ENVIRONMENT: system-wide variables\n" )
        for var in self.global_env:
            FILE.write( "export " + var + "=\"" + self.global_env[var] + "\"\n" )

        FILE.write( "\n# TASK EXECUTION ENVIRONMENT: task-specific variables:\n" )
        for var in self.task_env:
            FILE.write( "export " + var + "=\"" + self.task_env[var] + "\"\n" )

    def write_extra_scripting( self, FILE ):
        # override if required
        pass

    def write_cylc_scripting( self, FILE ):
        FILE.write( "\n" )
        FILE.write( ". $CYLC_DIR/cylc-env.sh\n" )

    def write_task_execute( self, FILE ):
        FILE.write( "\n" )
        FILE.write( self.task + " " + self.commandline + "\n\n" )

    def submit_jobfile_local( self, dry_run  ):
        # CONSTRUCT self.command, A LOCAL COMMAND THAT WILL SUBMIT THE
        # JOB THAT RUNS THE TASK. DERIVED CLASSES MUST PROVIDE THIS.
        self.construct_command()

        # make sure the jobfile is executable
        os.chmod( self.jobfile_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

        # run as owner, in owner's home directory, if owner is defined.
        # (write-permissions may be required in the running directory).
        changed_dir = False
        if self.owner and not job_submit.dummy_mode:
            if self.owner != os.environ['USER']:
                # change to the task owner's running directory before
                # submitting the job
                cwd = os.getcwd()
                try:
                    os.chdir( self.running_dir )
                except OSError, e:
                    print "Failed to change to task owner's running directory"
                    print e
                    return False
                else:
                    changed_dir = True
                    new_dir = self.running_dir

                self.command = 'sudo -u ' + self.owner + ' ' + self.command

        # execute the local command to submit the job
        if dry_run:
            print " > TASK EXECUTION SCRIPT: " + self.jobfile_path
            print " > JOB SUBMISSION METHOD: " + self.command
            success = True
        else:
            print " > SUBMITTING TASK: " + self.command
            try:
                res = subprocess.call( self.command, shell=True )
                if res < 0:
                    print "command terminated by signal", res
                    success = False
                elif res > 0:
                    print "command failed", res
                    success = False
                else:
                    # res == 0
                    success = True
            except OSError, e:
                # THIS DOES NOT CATCH BACKGROUND EXECUTION FAILURE
                # because subprocess.call( 'foo &' ) returns immediately
                # and the failure occurs in the detached sub-shell.
                print "Job submission failed", e
                success = False
           
        if changed_dir:
            # change back
            os.chdir( cwd )

        return success


    def submit_jobfile_remote( self, dry_run ):
        # make sure the local jobfile is executable (file mode is preserved by scp?)
        os.chmod( self.jobfile_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

        self.destination = self.remote_host
        if self.owner:
            self.destination = self.owner + '@' + self.remote_host

        # copy file to $HOME for owner on remote machine
        command_1 = 'scp ' + self.jobfile_path + ' ' + self.destination + ':'
        if dry_run:
            print " > LOCAL TASK EXECUTION SCRIPT:  " + self.jobfile_path
            print " > WOULD COPY TO REMOTE HOST AS: " + command_1
            success = True
        else:
            print " > COPYING TO REMOTE HOST: " + command_1
            try:
                res = subprocess.call( command_1, shell=True )
                if res < 0:
                    print "scp terminated by signal", res
                    success = False
                elif res > 0:
                    print "scp failed", res
                    success = False
                else:
                    # res == 0
                    success = True
            except OSError, e:
                # THIS DOES NOT CATCH BACKGROUND EXECUTION FAILURE
                # (i.e. cylc's simplest "background" job submit method)
                # because subprocess.call( 'foo &' ) returns immediately
                # and the failure occurs in the detached sub-shell.
                print "Failed to execute scp command", e
                success = False
 
        # now replace local jobfile path with remote jobfile path
        self.jobfile_path = '$HOME/' + os.path.basename( self.jobfile_path )

        self.construct_command()

        command_2 = "ssh " + self.destination + " '" + self.command + "'"

        # execute the local command to submit the job
        if dry_run:
            print " > REMOTE TASK EXECUTION SCRIPT: " + self.jobfile_path
            print " > REMOTE JOB SUBMISSION METHOD: " + command_2
        else:
            print " > SUBMITTING TASK: " + command_2
            try:
                res = subprocess.call( command_2, shell=True )
                if res < 0:
                    print "command terminated by signal", res
                    success = False
                elif res > 0:
                    print "command failed", res
                    success = False
                else:
                    # res == 0
                    success = True
            except OSError, e:
                # THIS DOES NOT CATCH REMOTE BACKGROUND EXECUTION FAILURE
                # (i.e. cylc's simplest "background" job submit method)
                # as subprocess.call( 'ssh dest "foo </dev/null &"' )
                # returns immediately and the failure occurs in the
                # remote background sub-shell.
                print "Job submission failed", e
                success = False
 
        return success


    def cleanup( self ):
        # called by task class when the job finishes
        print ' - deleting jobfile ' + self.jobfile_path
        os.unlink( self.jobfile_path )

        if self.remote_jobfile_path:
            print ' - deleting remote jobfile ' + self.remote_jobfile_path
            os.system( 'ssh ' + self.destination + ' rm ' + self.remote_jobfile_path )

#!/usr/bin/env python

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

import pwd
import re, os, sys
import tempfile, stat
import cycle_time
from interp_env import interp_self, interp_other, interp_local, interp_local_str, replace_delayed, interp_other_str, replace_delayed_str

try:
    import subprocess
    # see documentation in bin/cylc
    use_subprocess = True
except:
    use_subprocess = False
 
class job_submit:

    # class variables to be set by the task manager
    dummy_mode = False
    global_env = {}

    def set_owner_and_homedir( self, owner = None ):
        if owner:
            # owner can be defined using environment variables
            self.owner = self.interp_str( owner )
        else:
            self.owner = self.cylc_owner

        if not self.owner:
            self.homedir = os.environ[ 'HOME' ]
        else:
            try:
                self.homedir = pwd.getpwnam( self.owner )[5]
            except:
                raise SystemExit( "Task " + self.task_id + ", owner not found: " + self.owner )

    def set_running_dir( self ):
        # default to owner's home dir
        self.running_dir = self.homedir


    def interp_str( self, str ):
        str = interp_other_str( str, self.task_env )
        str = interp_other_str( str, job_submit.global_env )
        str = interp_local_str( str )
        str = replace_delayed_str( str )
        return str

    def __init__( self, task_id, ext_task, task_env, com_line, dirs, logs, owner, host ): 

        self.cylc_owner = os.environ['USER']

        # unique task identity
        self.task_id = task_id

        # in dummy mode, replace the real external task with the dummy task
        self.task = ext_task
        if job_submit.dummy_mode:
            self.task = "_cylc-dummy-task"

        # extract cycle time (cycling tasks) or tag (asynchronous tasks)
        # from the task id: NAME%CYCLE_TIME or NAME%TAG.
        ( self.task_name, tag ) = task_id.split( '%' )
        if cycle_time.is_valid( tag ):
            self.cycle_time = tag

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
        # prior to running the scheduler or submit!
        task_env[ 'TASK_ID'    ] = self.task_id
        task_env[ 'CYCLE_TIME' ] = self.cycle_time
        task_env[ 'TASK_NAME'  ] = self.task_name

        task_env = interp_self( task_env )
        task_env = interp_other( task_env, job_submit.global_env )
        task_env = interp_local( task_env )
        task_env = replace_delayed( task_env )

        # GLOBAL ENVIRONMENT: now extracted just before use in
        # write_environment() so that remote_switch can dynamically
        # reset the dummy mode CYLC_FAILOUT_ID variable.

        self.task_env = task_env

        # same for the task script command line
        commandline = ' '.join( com_line ) 
        self.commandline = self.interp_str( commandline )

        # same for external task, which may be defined in terms of
        # $[HOME], for example.
        self.task = self.interp_str( self.task )

        # queueing system directives
        self.directives  = dirs
        
        # directive prefix, e.g. '#QSUB ' (qsub), or '#@ ' (loadleveler)
        # OVERRIDE IN DERIVED CLASSES
        self.directive_prefix = "# DIRECTIVE-PREFIX "

        # final directive, WITH PREFIX, e.g. '#@ queue' for loadleveler
        self.final_directive = ""
        
        # a remote host can be defined using environment variables
        if host:
            self.remote_host = self.interp_str( host )
        else:
            self.remote_host = None

        # no need for task owner to be defined with environment variables?
        #if owner:
        #    owner = self.interp_str( owner )

        if job_submit.dummy_mode:
            # ignore defined owners in dummy mode, so that systems
            # containing owned tasks can be tested in dummy mode outside
            # of their normal execution environment.
            owner = None

        self.set_owner_and_homedir( owner )
        self.set_running_dir() 

        # a job submit log can be defined using environment variables
        logs.interpolate( job_submit.global_env )
        logs.interpolate( self.task_env )
        logs.interpolate()
        self.logfiles = logs

        self.jobfile_is_remote = False

    def submit( self, dry_run ):
        # CALL THIS TO SUBMIT THE TASK

        # Get a new temp filename.
        # TO DO: use [,dir=] argument and allow user to configure the
        # temporary directory. For now the default is should be ok
        # (it reads $TMPDIR, $TEMP, or $TMP)
        self.jobfile_path = tempfile.mktemp( prefix='cylc-') 
        
        # open the job file to write
        JOBFILE = open( self.jobfile_path, 'w' )

        # write the job file
        self.write_jobfile( JOBFILE )

        # close the jobfile
        JOBFILE.close() 

        # submit the file
        if self.remote_host and not job_submit.dummy_mode:
            return self.submit_jobfile_remote( dry_run )
        else:
            return self.submit_jobfile_local( dry_run )

    def write_jobfile( self, FILE ):
        FILE.write( '#!/bin/bash\n\n' )
        FILE.write( '# THIS IS A CYLC JOB SUBMISSION FILE FOR ' + self.task_id + '.\n' )
        FILE.write( '# It will be submitted to run by the "' + self.__class__.__name__ + '" method.\n\n' )
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
        FILE.write( self.final_directive + "\n\n" )

    def write_environment( self, FILE ):
        # write the environment scripting to the jobfile

        #for env in [ job_submit.global_env, self.task_env ]:

        # global env: see comment in __init__() environment section
        self.global_env = replace_delayed( job_submit.global_env )

        FILE.write( "# TASK EXECUTION ENVIRONMENT: system-wide variables\n" )
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
        FILE.write( "# CONFIGURE THE ENVIRONMENT FOR CYLC ACCESS.\n" )
        FILE.write( ". $CYLC_DIR/cylc-env.sh\n" )

    def write_task_execute( self, FILE ):
        FILE.write( "\n" )
        FILE.write( "# EXECUTE THE TASK.\n" )
        FILE.write( self.task + " " + self.commandline + "\n\n" )

    def submit_jobfile_local( self, dry_run  ):
        # CONSTRUCT self.command, A LOCAL COMMAND THAT WILL SUBMIT THE
        # JOB THAT RUNS THE TASK. DERIVED CLASSES MUST PROVIDE THIS.
        self.construct_command()

        # add local jobfile to list of viewable logfiles
        self.logfiles.replace_path( '/.*/cylc-.*', self.jobfile_path )

        # make sure the jobfile is executable
        os.chmod( self.jobfile_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

        # run as owner, in owner's home directory, if owner is defined.
        # (write-permissions may be required in the running directory).
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

        if self.owner != self.cylc_owner:
            self.command = 'sudo -u ' + self.owner + ' ' + self.command

        # execute the local command to submit the job
        if dry_run:
            print " > TASK EXECUTION SCRIPT: " + self.jobfile_path
            print " > JOB SUBMISSION METHOD: " + self.command
            success = True
        else:
            print " > SUBMITTING TASK: " + self.command

            if use_subprocess:
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
            else:
                #print "OS.SYSTEM: " + self.command
                os.system( self.command )
                success = True

        if changed_dir:
            # change back
            os.chdir( cwd )

        return success


    def submit_jobfile_remote( self, dry_run ):
        # make sure the local jobfile is executable (file mode is preserved by scp?)
        os.chmod( self.jobfile_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

        self.destination = self.remote_host
        self.destination = self.owner + '@' + self.remote_host

        # copy file to $HOME for owner on remote machine
        command_1 = 'scp ' + self.jobfile_path + ' ' + self.destination + ':'
        if dry_run:
            print " > LOCAL TASK EXECUTION SCRIPT:  " + self.jobfile_path
            print " > WOULD COPY TO REMOTE HOST AS: " + command_1
            success = True
        else:
            if use_subprocess:
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
            else:
                #print "OS.SYSTEM: " + command_1
                os.system( command_1 )
                success = True

        # now replace local jobfile path with remote jobfile path
        # (relative to $HOME)

        #disable jobfile deletion as we're adding it to the viewable logfile list
        #print ' - deleting local jobfile ' + self.jobfile_path
        #os.unlink( self.jobfile_path )

        # use explicit path to the location of the remote job submit file
        self.jobfile_path = '$HOME/' + os.path.basename( self.jobfile_path )
        self.jobfile_is_remote = True

        self.construct_command()

        command_2 = "ssh " + self.destination + " '" + self.command + "'"

        # execute the local command to submit the job
        if dry_run:
            print " > REMOTE TASK EXECUTION SCRIPT: " + self.jobfile_path
            print " > REMOTE JOB SUBMISSION METHOD: " + command_2
        else:
            print " > SUBMITTING TASK: " + command_2
            if use_subprocess:
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
 
            else:
                #print "OS.SYSTEM: " + command_2
                os.system( command_2 )
                success = True

        return success


    def cleanup( self ):
        # called by task class when the job finishes
        
        # DISABLE JOBFILE DELETION AS WE'RE ADDING IT TO THE VIEWABLE LOGFILE LIST
        return 

        if self.jobfile_is_remote:
            print ' - deleting remote jobfile ' + self.jobfile_path
            os.system( 'ssh ' + self.destination + ' rm ' + self.jobfile_path )
        else:
            print ' - deleting local jobfile ' + self.jobfile_path
            os.unlink( self.jobfile_path )

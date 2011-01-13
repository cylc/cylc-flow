#!/usr/bin/env python

# TO DO: UPDATE, MOVE, OR DELETE THIS DOCUMENTATION:
        # REMOTE TASKS MUST DEFINE (the remote) CYLC_DIR and
        # CYLC_SUITE_DIR in the taskdef file %ENVIRONMENT key
        # (full path with no interpolation).  The new (remote) values
        # will will replace the original (local) values in big_env
        # above (then full path to remote task script not required - if
        # in the remote $CYLC_SUITE_DIR/scripts).

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
 
dummy_job_succeed = 'cylc-wrapper -m "echo $TASK_ID - DUMMY MODE; sleep $CYLC_DUMMY_SLEEP"'
dummy_job_fail    = 'cylc-wrapper -m "echo $TASK_ID - DUMMY MODE - ABORTING BY USER REQUEST; /bin/false"'

class job_submit(object):
    # class variables to be set by the task manager
    dummy_mode = False
    failout_id = None
    ####global_env = {}

    def interp_str( self, str ):
        str = interp_other_str( str, self.task_env )
        str = interp_other_str( str, self.__class__.global_env )
        str = interp_local_str( str )
        str = replace_delayed_str( str )
        return str

    def use_dummy_task( self ):
        # $CYLC_DUMMY_SLEEP is set at start up
        if self.__class__.failout_id != self.task_id:
            self.task = dummy_job_succeed
        else: 
            self.task = dummy_job_fail

    def __init__( self, task_id, ext_task, task_env, dirs, extra, logs, owner, host ): 

        # TO DO: The GLOBAL ENVIRONMENT is currently extracted just
        # before use in write_environment(). This WAS so that
        # remote_switch could dynamically reset the dummy mode
        # CYLC_FAILOUT_ID variable - but dummy failouts are now handled
        # differently so we could bring the global env back here.
        self.task_env = task_env
        # task_env is needed by the call to inter_str() immediately below.
 
        # username under which the suite is running
        self.cylc_owner = os.environ['USER']
        # task owner
        if owner:
            # owner can be defined using environment variables
            self.owner = self.interp_str( owner )
        else:
            self.owner = self.cylc_owner

        # unique task identity
        self.task_id = task_id
        # command to run
        self.task = ext_task

        # extract cycle time (cycling tasks) or tag (asynchronous tasks)
        # from the task id: NAME%CYCLE_TIME or NAME%TAG.
        ( self.task_name, tag ) = task_id.split( '%' )
        if cycle_time.is_valid( tag ):
            self.cycle_time = tag

        # The values of task-specific environment variables defined in
        # the taskdef file may reference other task-specific 
        # global cylc environment variables $FOO, ${FOO}, ${FOO#_*nc}
        # etc. Thus we ensure that the order of definition is preserved
        # and parse any such references through as-is to the job script.

        ### INTERP OF TASK PATH NOT REQUIRED:
        #### self.task = self.interp_str( self.task )

        # queueing system directives
        self.directives  = dirs

        # extra scripting
        self.extra_scripting = extra
        
        # directive prefix, e.g. '#QSUB ' (qsub), or '#@ ' (loadleveler)
        # OVERRIDE IN DERIVED CLASSES
        self.directive_prefix = "# DIRECTIVE-PREFIX "

        # final directive, WITH PREFIX, e.g. '#@ queue' for loadleveler
        self.final_directive = ""
        
        if host and not self.__class__.dummy_mode:
            # REMOTE JOB SUBMISSION as owner
            self.local_job_submit = False
            # a remote host can be defined using environment variables
            self.remote_host = self.interp_str( host )

        else:
            # LOCAL JOB SUBMISSION as owner
            self.local_job_submit = True

            if self.__class__.dummy_mode:
                # ignore defined task owners in dummy mode, so that suites
                # containing owned tasks can be tested in dummy mode outside
                # of their normal execution environment.
                self.owner = self.cylc_owner
                # ignore the scripting section in dummy mode
                self.extra_scripting = ''

            # The job will be submitted from the owner's home directory,
            # in case the job submission method requires that the
            # "running directory" exists - the only directory we can be
            # sure exists in advance is the home directory; in general
            # it is difficult to create a new directory on the fly if it
            # must exist *before the job is submitted*.  E.g. for tasks
            # that we 'sudo llsubmit' as another owner, sudo would have
            # to be explicitly configured to allow use of 'mkdir' as
            # well as 'llsubmit' (llsubmitting a special directory
            # creation script in advance, *and* detect when it has
            # finished, is too complicated).
 
            try:
                self.homedir = pwd.getpwnam( self.owner )[5]
            except:
                raise SystemExit( "Task " + self.task_id + ", owner not found: " + self.owner )

        # a job submit log can be defined using environment variables
        logs.interpolate( self.__class__.global_env )
        logs.interpolate( self.task_env )
        logs.interpolate()
        self.logfiles = logs

    def submit( self, dry_run ):
        # CALL THIS TO SUBMIT THE TASK

        if self.__class__.dummy_mode:
            # this is done here so that it also happens
            # after resetting a dummy failout task.
            self.use_dummy_task()

        # Get a new temp filename.
        # TO DO: use [,dir=] argument and allow user to configure the
        # temporary directory. For now the default is should be ok
        # (it reads $TMPDIR, $TEMP, or $TMP)
        self.jobfile_path = tempfile.mktemp( prefix='cylc-' + self.task_id + '-' ) 
        
        # open the job file to write
        JOBFILE = open( self.jobfile_path, 'w' )

        # write the job file
        self.write_jobfile( JOBFILE )

        # close the jobfile
        JOBFILE.close() 

        # submit the file
        if not self.local_job_submit:
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

        #for env in [ self.__class__.global_env, self.task_env ]:

        # global env: see comment in __init__() environment section
        #### self.global_env = replace_delayed( self.__class__.global_env )

        FILE.write( "# TASK EXECUTION ENVIRONMENT global variables:\n" )
        for var in self.global_env:
            FILE.write( "export " + var + "=\"" + str( self.global_env[var] ) + "\"\n" )

        FILE.write( "\n# TASK EXECUTION ENVIRONMENT task variables:\n" )
        for var in self.task_env:
            FILE.write( "export " + var + "=\"" + str( self.task_env[var] ) + "\"\n" )

    def write_extra_scripting( self, FILE ):
        # override if required
        FILE.write( "\n" )
        FILE.write( "# SCRIPTING:\n" )
        FILE.write( self.extra_scripting + '\n' )

    def write_cylc_scripting( self, FILE ):
        FILE.write( "\n" )
        FILE.write( "# CONFIGURE THE ENVIRONMENT FOR CYLC:\n" )
        FILE.write( ". $CYLC_DIR/cylc-env.sh\n" )

    def write_task_execute( self, FILE ):
        FILE.write( "\n" )
        FILE.write( "# EXECUTE THE TASK:\n" )
        FILE.write( self.task + "\n\n" )

    def submit_jobfile_local( self, dry_run  ):
        # CONSTRUCT self.command, A LOCAL COMMAND THAT WILL SUBMIT THE
        # JOB THAT RUNS THE TASK. DERIVED CLASSES MUST PROVIDE THIS.
        self.construct_command()

        # add local jobfile to list of viewable logfiles
        self.logfiles.replace_path( '/.*/cylc-.*', self.jobfile_path )

        # make sure the jobfile is executable
        os.chmod( self.jobfile_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

        cwd = os.getcwd()
        try: 
            os.chdir( self.homedir )
        except OSError, e:
            print "Failed to change to task owner's home directory"
            print e
            return False
        else:
            changed_dir = True
            new_dir = self.homedir

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
                os.system( self.command )
                success = True

        #if changed_dir:
        #    # change back
        #    os.chdir( cwd )

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
                os.system( command_1 )
                success = True

        # now replace local jobfile path with remote jobfile path
        # (relative to $HOME)

        #disable jobfile deletion as we're adding it to the viewable logfile list
        #print ' - deleting local jobfile ' + self.jobfile_path
        #os.unlink( self.jobfile_path )

        # use explicit path to the location of the remote job submit file
        self.jobfile_path = '$HOME/' + os.path.basename( self.jobfile_path )

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
                os.system( command_2 )
                success = True

        return success


    def cleanup( self ):
        # called by task class when the job finishes
        
        # DISABLE JOBFILE DELETION AS WE'RE ADDING IT TO THE VIEWABLE LOGFILE LIST
        return 

        if not self.local_job_submit:
            print ' - deleting remote jobfile ' + self.jobfile_path
            os.system( 'ssh ' + self.destination + ' rm ' + self.jobfile_path )
        else:
            print ' - deleting local jobfile ' + self.jobfile_path
            os.unlink( self.jobfile_path )

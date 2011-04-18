#!/usr/bin/env python

"""
Job submission base class.

Writes a temporary "job file" that exports the cylc execution
environment (so the executing task can access cylc commands), suite
global and task-specific environment variables, and then  
executes the task command.  Specific derived job submission classes
define the means by which the job file itself is executed.

If OWNER is defined and REMOTE_HOST is not, submit locally by:
 sudo -u OWNER submit(FILE) 
OR
 ssh OWNER@localhost submit(FILE)
so passwordless ssh to localhost as OWNER must be configured.
 
If REMOTE_HOST is defined and OWNER is not, the job file is submitted
by copying it to the remote host with scp, and executing the defined
submit(FILE) on the remote host by ssh. Passwordless ssh to the remote
host must be configured. 

If REMOTE_HOST and OWNER are defined, we scp and ssh to
 'OWNER@REMOTE_HOST'
so passwordless ssh to remote host as OWNER must be configured.
"""

import pwd
import random
import re, os
import tempfile, stat
import string
from mkdir_p import mkdir_p
from jobfile import jobfile
from dummy import dummy_command, dummy_command_fail
import subprocess
 
class job_submit(object):
    # class variables that are set remotely at startup:
    # (e.g. 'job_submit.dummy_mode = True')
    dummy_mode = False
    failout_id = None
    global_pre_scripting = None
    global_post_scripting = None
    global_env = None
    cylc_env = None
    owned_task_execution_method = None

    def __init__( self, task_id, task_command, task_env, directives, 
            pre_scripting, post_scripting, logfiles, task_joblog_dir, 
            task_owner, remote_host ): 

        self.task_id = task_id
        self.task_command = task_command
        self.task_env = task_env
        self.directives  = directives
        self.task_pre_scripting = pre_scripting
        self.task_post_scripting = post_scripting
        self.logfiles = logfiles
 
        self.suite_owner = os.environ['USER']
        if task_owner:
            self.task_owner = task_owner
            self.other_owner = True
        else:
            self.task_owner = self.suite_owner
            self.other_owner = False

        if remote_host:
            # Remote job submission
            if self.__class__.dummy_mode:
                # Ignore remote hosts in dummy mode (this allows us to
                # dummy-run suites with remote tasks if outside of their 
                # usual execution environment).
                pass
            else:
                self.local_job_submit = False
                self.remote_host = remote_host
                self.homedir = None
                # (remote job submission by ssh will automatically dump
                # us in the owner's home directory)
        else:
            # Local job submission
            self.local_job_submit = True
            if self.__class__.dummy_mode:
                # Ignore task owners in dummy mode (this allows us to
                # dummy-run suites with owned tasks if outside of their 
                # usual execution environment).
                self.task_owner = self.suite_owner

            # The job will be submitted from the task owner's home
            # directory, in case the job submission method requires that
            # the "running directory" exists and is writeable by the job
            # owner (e.g. loadleveler?). The only directory we can be
            # sure exists in advance is the home directory; in general
            # it is difficult to create a new directory on the fly if it
            # must exist *before the job is submitted*. E.g. for tasks
            # that we 'sudo llsubmit' as another owner, sudo would have
            # to be configured to allow use of 'mkdir' as well as
            # 'llsubmit' (to llsubmit a special directory creation
            # script in advance *and* detect when it has finished is
            # difficult, and cylc would hang while the process was
            # running).
            try:
                self.homedir = pwd.getpwnam( self.task_owner )[5]
            except:
                raise SystemExit( "ERROR: task " + self.task_id + " owner (" + self.task_owner + "): home dir not found" )

        # Job submission log directory
        # (for owned and remote tasks, this directory must exist in
        # advance; otherwise cylc can create it if necessary).
        if task_joblog_dir:
            # task overrode the suite job submission log directory
            jldir = os.path.expandvars( os.path.expanduser(task_joblog_dir))
            self.joblog_dir = jldir
            if self.local_job_submit and not self.task_owner:
                mkdir_p( jldir )
        else:
            # use the suite job submission log directory
            # (created if necessary in config.py)
            self.joblog_dir = self.__class__.joblog_dir

        if not self.local_job_submit:
            # Make joblog_dir relative to $HOME for remote tasks by
            # cutting the suite owner's $HOME from the path (if it exists;
            # if not - e.g. remote path specified absolutely - this will
            # have no effect).
            self.joblog_dir = re.sub( os.environ['HOME'] + '/', '', self.joblog_dir )
        else:
            # local jobs
            if self.other_owner:
                # make joblogdir relative to owner's home dir
                self.joblog_dir = re.sub( os.environ['HOME'], self.homedir, self.joblog_dir )
            else:
                pass

        # Generate stdout and stderr log files
        if self.local_job_submit:
            # can get a unique name locally using tempfile
            self.stdout_file = tempfile.mktemp( 
                prefix = self.task_id + "-",
                suffix = ".out", 
                dir = self.joblog_dir )
            self.stderr_file = re.sub( '\.out$', '.err', self.stdout_file )
        else:
            # Remote jobs are submitted from remote $HOME, via ssh.
            # Can't use tempfile remotely so generate a random string. 
            rnd = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(6))
            self.stdout_file = self.task_id + '-' + rnd + '.out'
            self.stderr_file = self.task_id + '-' + rnd + '.err'

        # Overrideable methods to be used by derived classes to modify stuff
        self.set_directives()
        self.set_scripting()
        self.set_environment()
 
    def set_directives( self ):
        # OVERRIDE IN DERIVED CLASSES IF NECESSARY
        # self.directives['name'] = value

        # Prefix, e.g. '#QSUB ' (qsub), or '#@ ' (loadleveler)
        self.directive_prefix = "# FOO "
        # Final directive, WITH PREFIX, e.g. '#@ queue' for loadleveler
        self.final_directive = " # FINAL"

    def set_scripting( self ):
        # OVERRIDE IN DERIVED CLASSES IF NECESSARY
        # to modify pre- and post-command scripting
        return

    def set_environment( self ):
        # OVERRIDE IN DERIVED CLASSES IF NECESSARY
        # to modify global or task-specific environment
        return

    def construct_jobfile_submission_command( self ):
        # DERIVED CLASSES MUST OVERRIDE.
        # Construct self.command, a command to submit the job file to
        # run by the derived job submission method.
        raise SystemExit( 'ERROR: no job submission command defined!' )

    def submit( self, dry_run ):
        if self.__class__.dummy_mode:
            # do this in submit() so that a dummy mode failout task 
            # can be reset on resubmission (TO DO - check this).
            if self.__class__.failout_id != self.task_id:
                self.task_command = dummy_command
            else: 
                self.task_command = dummy_command_fail

        # Record local logs for access by gcylc (or replace existing
        # ones in case the job is resubmitted by the suite operator)
        self.logfiles.replace_path( '/.*/' + self.task_id + '-.*\.out', self.stdout_file )
        self.logfiles.replace_path( '/.*/' + self.task_id + '-.*\.err', self.stderr_file )

        jf = jobfile( self.task_id, 
                self.__class__.cylc_env, self.__class__.global_env, self.task_env, 
                self.__class__.global_pre_scripting, self.__class__.global_post_scripting, 
                self.task_pre_scripting, self.task_post_scripting, 
                self.directive_prefix, self.directives, self.task_command, 
                self.__class__.shell, self.__class__.dummy_mode,
                self.__class__.__name__ )
        self.jobfile_path = jf.write()

        # Construct self.command, the command to submit the jobfile to run
        self.construct_jobfile_submission_command()

        # Now submit it
        if self.local_job_submit:
            return self.submit_jobfile_local( dry_run )
        else:
            return self.submit_jobfile_remote( dry_run )

    def submit_jobfile_local( self, dry_run  ):
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

        if self.task_owner != self.suite_owner:
            if self.__class__.owned_task_execution_method == 'sudo':
                self.command = 'sudo -u ' + self.task_owner + ' ' + self.command
            elif self.__class__.owned_task_execution_method == 'ssh': 
                # TO DO: to allow remote hangup we must use: 
                # 'ssh foo@bar baz </dev/null &'
                # (only for direct exec? OK if baz is llsubmit, qsub, etc.?
                self.command = 'ssh ' + self.task_owner + '@localhost ' + self.command
            else:
                # this should not happen
                raise SystemExit( 'ERROR:, unknown owned task execution method: ' + self.__class__.owned_task_execution_method )

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

        #if changed_dir:
        #    # change back
        #    os.chdir( cwd )

        return success

    def submit_jobfile_remote( self, dry_run ):
        # make sure the local jobfile is executable (file mode is preserved by scp?)
        os.chmod( self.jobfile_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

        self.destination = self.remote_host
        self.destination = self.task_owner + '@' + self.remote_host

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

        #disable jobfile deletion as we're adding it to the viewable logfile list
        #print ' - deleting local jobfile ' + self.jobfile_path
        #os.unlink( self.jobfile_path )

        # Replace local with remote jobfile path (relative to $HOME).
        self.jobfile_path = '$HOME/' + os.path.basename( self.jobfile_path )

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
        
        # DISABLE JOBFILE DELETION AS WE'RE ADDING IT TO THE VIEWABLE LOGFILE LIST
        return 

        if not self.local_job_submit:
            print ' - deleting remote jobfile ' + self.jobfile_path
            os.system( 'ssh ' + self.destination + ' rm ' + self.jobfile_path )
        else:
            print ' - deleting local jobfile ' + self.jobfile_path
            os.unlink( self.jobfile_path )

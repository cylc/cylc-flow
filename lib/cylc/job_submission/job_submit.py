#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Job submission base class.

Writes a temporary "job file" that exports the cylc execution
environment (so the executing task can access cylc commands), suite
global and task-specific environment variables, and then  
executes the task command.  Specific derived job submission classes
define the means by which the job file itself is executed.

If OWNER@REMOTE_HOST is not equivalent to whoami@localhost:
 ssh OWNER@HOST submit(FILE)
so passwordless ssh must be configured.
"""

import pwd
import re, os
import tempfile, stat
import string
from cylc.mkdir_p import mkdir_p
from jobfile import jobfile
from cylc.dummy import dummy_command, dummy_command_fail
import socket
import subprocess
#import datetime
import time
 
class job_submit(object):
    REMOTE_COMMAND_TEMPLATE = ( " '"
                                + "mkdir -p $(dirname %(jobfile_path)s)"
                                + " && cat >%(jobfile_path)s"
                                + " && chmod +x %(jobfile_path)s"
                                + " && (%(command)s)"
                                + "'" )
    SUDO_TEMPLATE = "sudo -u %s"

    # class variables that are set remotely at startup:
    # (e.g. 'job_submit.simulation_mode = True')
    simulation_mode = False
    global_task_owner = None
    global_remote_host = None
    global_remote_shell_template = None
    global_remote_cylc_dir = None
    global_remote_suite_dir = None
    global_manual_messaging = False
    failout_id = None
    global_pre_scripting = None
    global_post_scripting = None
    global_env = None
    global_dvs = None
    cylc_env = None
    owned_task_execution_method = None
    global_job_submit_command_template = None

    def __init__( self, task_id, task_command, task_env, directives, 
            manual_messaging, logfiles, task_joblog_dir, task_owner,
            remote_host, remote_cylc_dir, remote_suite_dir,
            remote_shell_template=None, job_submit_command_template=None ): 

        self.task_id = task_id
        self.task_command = task_command
        if self.__class__.simulation_mode:
            if self.__class__.failout_id != self.task_id:
                self.task_command = dummy_command
            else: 
                self.task_command = dummy_command_fail

        self.task_env = task_env
        self.directives  = directives
        self.logfiles = logfiles
 
        self.suite_owner = os.environ['USER']
        if task_owner:
            self.task_owner = task_owner
            self.other_owner = True
        elif self.__class__.global_task_owner:
            self.task_owner = self.__class__.global_task_owner
            self.other_owner = True
        else:
            self.task_owner = self.suite_owner
            self.other_owner = False

        if remote_shell_template:
            self.remote_shell_template = remote_shell_template
        elif self.__class__.global_remote_shell_template:
            self.remote_shell_template = self.__class__.global_remote_shell_template
        else:
            self.remote_shell_template = None

        if job_submit_command_template:
            self.job_submit_command_template = job_submit_command_template
        elif self.__class__.global_job_submit_command_template:
            self.job_submit_command_template = self.__class__.global_job_submit_command_template
        else:
            self.job_submit_command_template = None

        if remote_cylc_dir:
            self.remote_cylc_dir = remote_cylc_dir
        elif self.__class__.global_remote_cylc_dir:
            self.remote_cylc_dir = self.__class__.global_remote_cylc_dir
        else:
            self.remote_cylc_dir = None
  
        if remote_suite_dir:
            self.remote_suite_dir = remote_suite_dir
        elif self.__class__.global_remote_suite_dir:
            self.remote_suite_dir = self.__class__.global_remote_suite_dir
        else:
            self.remote_suite_dir = None

        if remote_host:
            self.remote_host = remote_host
        elif self.__class__.global_remote_host:
            self.remote_host = self.__class__.global_remote_host
        else:
            self.remote_host = "localhost"

        self.local_job_submit = (
                ( not self.remote_host
                  or self.remote_host == "localhost"
                  or self.remote_host == socket.gethostname() )
            and self.task_owner == self.suite_owner
        )

        if manual_messaging != None:  # boolean, must distinguish None from False
            self.manual_messaging = manual_messaging
        elif self.__class__.global_manual_messaging != None:  # (ditto)
            self.manual_messaging = self.__class__.global_manual_messaging

        if self.__class__.simulation_mode:
            # but ignore remote task settings in simulation mode (this allows us to
            # dummy-run suites with remote tasks if outside of their 
            # usual execution environment).
            self.local_job_submit = True
            # Ignore task owners in simulation mode (this allows us to
            # dummy-run suites with owned tasks if outside of their 
            # usual execution environment).
            self.task_owner = self.suite_owner

        # The job will be submitted from the task owner's home
        # directory, in case the job submission method requires that
        # the "running directory" exists and is writeable by the job
        # owner (e.g. loadleveler?). The only directory we can be
        # sure exists in advance is the home directory; in general
        # it is difficult to create a new directory on the fly if it
        # must exist *before the job is submitted*.
        try:
            self.homedir = pwd.getpwnam( self.task_owner ).pw_dir
        except:
            raise SystemExit( "ERROR: task %s owner (%s): home dir not found"
                              % (self.task_id, self.task_owner) )

        # Job submission log directory
        # (for owned and remote tasks, this directory must exist in
        # advance; otherwise cylc can create it if necessary).
        if task_joblog_dir:
            # task overrode the suite job submission log directory
            self.joblog_dir = task_joblog_dir
        else:
            # use the suite job submission log directory
            # (created if necessary in config.py)
            self.joblog_dir = self.__class__.joblog_dir

        self.joblog_dir = os.path.expandvars( os.path.expanduser(self.joblog_dir) )
        mkdir_p( self.joblog_dir )

        if not self.local_job_submit:
            # Make joblog_dir relative to $HOME for remote tasks by
            # cutting the suite owner's $HOME from the path (if it exists;
            # if not - e.g. remote path specified absolutely - this will
            # have no effect).
            self.joblog_dir = re.sub( os.environ['HOME'] + '/', '', self.joblog_dir )

        self.set_logfile_names()
        # Overrideable methods
        self.set_directives()  # (logfiles used here!)
        self.set_scripting()
        self.set_environment()
 
    def set_logfile_names( self ):
        # EITHER: Tag file name with a string that is the microseconds since epoch
        now = time.time()
        key = self.task_id + "-%.6f" % now
        # OR: with a similar string based on current date/time
        # now = datetime.datetime.now()
        # key = self.task_id + now.strftime("-%Y%m%dT%H%M%S.") + str(now.microsecond)
        self.jobfile_path = os.path.join( self.joblog_dir, key )
        self.stdout_file = self.jobfile_path + ".out"
        self.stderr_file = self.jobfile_path + ".err"

        # Record local logs for access by gcylc
        self.logfiles.add_path( self.stdout_file )
        self.logfiles.add_path( self.stderr_file )
        self.logfiles.add_path( self.jobfile_path )

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
        # change to $HOME 
        try: 
            os.chdir( pwd.getpwnam(self.suite_owner).pw_dir )
        except OSError, e:
            print "Failed to change to suite owner's home directory"
            print e
            return False

        jf = jobfile( self.task_id, 
                self.__class__.cylc_env, self.__class__.global_env, self.task_env, 
                self.__class__.global_pre_scripting, self.__class__.global_post_scripting, 
                self.directive_prefix, self.__class__.global_dvs, self.directives,
                self.final_directive, self.manual_messaging, self.task_command, 
                self.remote_cylc_dir, self.remote_suite_dir, 
                self.__class__.shell, self.__class__.simulation_mode,
                self.__class__.__name__ )
        jf.write( self.jobfile_path )

        if not self.local_job_submit:
            self.local_jobfile_path = self.jobfile_path
            self.remote_jobfile_path = self.jobfile_path

        # Construct self.command, the command to submit the jobfile to run
        self.construct_jobfile_submission_command()

        # make sure the jobfile is executable
        os.chmod( self.jobfile_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

        # configure command for local or remote submit
        if self.local_job_submit:
            command = self.command
            jobfile_path = self.jobfile_path
            stdin = None
        elif self.remote_host == "localhost" \
             and self.__class__.owned_task_execution_method == "sudo":
            # change to task owner's $HOME 
            try: 
                os.chdir( self.homedir )
            except OSError, e:
                print "Failed to change to task owner's home directory"
                print e
                return False

            command = self.SUDO_TEMPLATE % self.task_owner
            command += self.REMOTE_COMMAND_TEMPLATE % { "jobfile_path": self.jobfile_path,
                                                        "command": self.command }
            stdin = subprocess.PIPE
        else:
            self.destination = self.task_owner + "@" + self.remote_host
            remote_shell_template = self.remote_shell_template
            command = remote_shell_template % self.destination
            command += self.REMOTE_COMMAND_TEMPLATE % { "jobfile_path": self.jobfile_path,
                                                        "command": self.command }
            jobfile_path = self.destination + ":" + self.remote_jobfile_path
            stdin = subprocess.PIPE

        # execute the local command to submit the job
        if dry_run:
            print " > TASK JOB SCRIPT: " + jobfile_path
            print " > JOB SUBMISSION: " + command
            return True

        print " > SUBMITTING TASK: " + command
        try:
            popen = subprocess.Popen( command, shell=True, stdin=stdin )
            if not self.local_job_submit:
                f = open(self.jobfile_path)
                popen.communicate(f.read())
                f.close()
            res = popen.wait()
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
            # (i.e. cylc's simplest "background" job submit method)
            # because a background job returns immediately and the failure
            # occurs in the background sub-shell.
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

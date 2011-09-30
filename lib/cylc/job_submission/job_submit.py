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

Writes a temporary "job file" that exports the cylc environment (so the
executing task can access cylc commands), suite environment, and then  
executes the task command scripting. Derived job submission classes
define the means by which the job file itself is executed.

If OWNER@REMOTE_HOST is not equivalent to whoami@localhost:
   ssh OWNER@HOST submit(FILE)
so passwordless ssh must be configured.
"""

import pwd
import re, os, sys
from cylc.mkdir_p import mkdir_p
import stat
import string
from jobfile import jobfile
import socket
import subprocess
import time
 
class job_submit(object):
    REMOTE_COMMAND_TEMPLATE = ( " '"
            + "mkdir -p $(dirname %(jobfile_path)s)"
            + " && cat >%(jobfile_path)s"
            + " && chmod +x %(jobfile_path)s"
            + " && (%(command)s)"
            + "'" )
 
    # class variables that are set remotely at startup:
    # (e.g. 'job_submit.simulation_mode = True')
    simulation_mode = False
    failout_id = None
    cylc_env = None

    def __init__( self, task_id, pre_command, task_command,
            post_command, task_env, ns_hier, directives, 
            manual_messaging, logfiles, log_dir, share_dir, work_dir, task_owner,
            remote_host, remote_cylc_dir, remote_suite_dir,
            remote_shell_template, remote_log_dir, 
            job_submit_command_template, job_submission_shell ): 

        self.task_id = task_id
        self.pre_command = pre_command
        self.task_command = task_command
        self.post_command = post_command
        if self.__class__.simulation_mode and self.__class__.failout_id == self.task_id:
            self.task_command = '/bin/false'

        self.task_env = task_env
        self.namespace_hierarchy = ns_hier
        self.directives  = directives
        self.logfiles = logfiles
 
        self.share_dir = share_dir
        self.work_dir = work_dir
        self.job_submit_command_template = job_submit_command_template
        self.job_submission_shell = job_submission_shell

        if manual_messaging != None:  # boolean, must distinguish None from False
            self.manual_messaging = manual_messaging

        # Local job script path: Tag with microseconds since epoch
        # (used by both local and remote tasks)
        now = time.time()
        tag = self.task_id + "-%.6f" % now
        self.local_jobfile_path = os.path.join( log_dir, tag )
        # The directory is created in config.py
        self.logfiles.add_path( self.local_jobfile_path )

        # Local stdout and stderr log file paths:
        self.stdout_file = self.local_jobfile_path + ".out"
        self.stderr_file = self.local_jobfile_path + ".err"
        # Record paths of local log files for access by gcylc
        # (only works for remote tasks if there is a shared file system or
        # the output files are returned by, for instance, a hook script)
        self.logfiles.add_path( self.stdout_file)
        self.logfiles.add_path( self.stderr_file)
        
        self.suite_owner = os.environ['USER']
        self.remote_shell_template = remote_shell_template
        self.remote_cylc_dir = remote_cylc_dir
        self.remote_suite_dir = remote_suite_dir

        # Use remote job submission if (a) not simulation mode, (b) a
        # remote host is defined or task owner is defined.
        if not self.__class__.simulation_mode and \
            ( remote_host and remote_host != "localhost" and remote_host != socket.gethostname() ) or \
            ( task_owner and task_owner != self.suite_owner ):
            # REMOTE
            self.local = False
            if task_owner:
                self.task_owner = task_owner
            else:
                self.task_owner = self.suite_owner

            if remote_host:
                self.remote_host = remote_host
            else:
                self.remote_host = socket.gethostname()

            # Remote job script and stdout and stderr logs:
            self.remote_jobfile_path = os.path.join( remote_log_dir, tag )
            self.stdout_file = self.remote_jobfile_path + ".out"
            self.stderr_file = self.remote_jobfile_path + ".err"
            # Used in command construction:
            self.jobfile_path = self.remote_jobfile_path
        else:
            # LOCAL
            self.local = True
            self.task_owner = self.suite_owner
            # Used in command construction:
            self.jobfile_path = self.local_jobfile_path

        # Overrideable methods
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
        try: 
            os.chdir( pwd.getpwnam(self.suite_owner).pw_dir )
        except OSError, e:
            print >> sys.stderr, "Failed to change to suite owner's home directory"
            print >> sys.stderr, e
            return False

        jf = jobfile( self.task_id, 
                self.__class__.cylc_env, self.task_env, self.namespace_hierarchy, 
                self.directive_prefix, self.directives, self.final_directive, 
                self.manual_messaging, self.pre_command,
                self.task_command, self.post_command,
                self.remote_cylc_dir, self.remote_suite_dir, 
                self.job_submission_shell, 
                self.share_dir,
                self.work_dir,
                self.__class__.simulation_mode,
                self.__class__.__name__ )
        # write the job file
        jf.write( self.local_jobfile_path )
        # make it executable
        os.chmod( self.local_jobfile_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )
        print "GENERATED JOB SCRIPT: " + self.local_jobfile_path

        # Construct self.command, the command to submit the jobfile to run
        self.construct_jobfile_submission_command()
    
        if self.local or self.simulation_mode:
            stdin = None
            command = self.command
        else:
            stdin = subprocess.PIPE
            command = self.__class__.REMOTE_COMMAND_TEMPLATE % { "jobfile_path": self.jobfile_path, "command": self.command }
            destination = self.task_owner + "@" + self.remote_host
            command = self.remote_shell_template % destination + command

        # execute the local command to submit the job
        if dry_run:
            print "THIS IS A DRY RUN. HERE'S HOW I WOULD SUBMIT THE TASK:"
            print command
            return True

        print "SUBMITTING TASK: " + command
        try:
            popen = subprocess.Popen( command, shell=True, stdin=stdin )
            if not self.local:
                f = open(self.local_jobfile_path)
                popen.communicate(f.read())
                f.close()
            res = popen.wait()
            if res < 0:
                print >> sys.stderr, "command terminated by signal", res
                success = False
            elif res > 0:
                print >> sys.stderr, "command failed", res
                success = False
            else:
                # res == 0
                success = True
        except OSError, e:
            # THIS DOES NOT CATCH BACKGROUND EXECUTION FAILURE
            # (i.e. cylc's simplest "background" job submit method)
            # because a background job returns immediately and the failure
            # occurs in the background sub-shell.
            print >> sys.stderr, "Job submission failed", e
            success = False
            raise

        return success


#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

import pwd, re, sys, os
import stat
import string
from jobfile import jobfile
import socket
import subprocess
import time
from cylc.owner import user

class job_submit(object):
    REMOTE_COMMAND_TEMPLATE = ( " '"
            + "test -f /etc/profile && . /etc/profile 1>/dev/null 2>&1;"
            + "test -f $HOME/.profile && . $HOME/.profile 1>/dev/null 2>&1;"
            + " mkdir -p $(dirname %(jobfile_path)s)"
            + " && cat >%(jobfile_path)s"
            + " && chmod +x %(jobfile_path)s"
            + " && (%(command)s)"
            + "'" )

    # class variables that are set remotely at startup:
    # (e.g. 'job_submit.simulation_mode = True')
    simulation_mode = False
    failout_id = None
    cylc_env = None

    def __init__( self, task_id, initial_scripting, pre_command, task_command,
            try_number, post_command, task_env, ns_hier, directives,
            manual_messaging, logfiles, log_dir, share_dir, work_dir, task_owner,
            remote_host, remote_cylc_dir, remote_suite_dir,
            remote_shell_template, remote_log_dir,
            job_submit_command_template, job_submission_shell ):

        self.try_number = try_number
        self.task_id = task_id
        self.initial_scripting = initial_scripting
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

        self.suite_owner = user
        self.remote_shell_template = remote_shell_template
        self.remote_cylc_dir = remote_cylc_dir
        self.remote_suite_dir = remote_suite_dir

        # Use remote job submission if (a) not simulation mode, (b) a
        # remote host is defined or task owner is defined.
        if not self.__class__.simulation_mode and \
            ( remote_host and remote_host != "localhost" and remote_host != socket.gethostname() ) or \
            ( task_owner and task_owner != self.suite_owner ):
            # REMOTE TASKS
            self.local = False
            if task_owner:
                self.task_owner = task_owner
            else:
                self.task_owner = self.suite_owner

            if remote_host:
                self.remote_host = remote_host
            else:
                self.remote_host = socket.gethostname()

            self.remote_jobfile_path = os.path.join( remote_log_dir, tag )

            # Remote log files
            self.stdout_file = self.remote_jobfile_path + ".out"
            self.stderr_file = self.remote_jobfile_path + ".err"

            # Used in command construction:
            self.jobfile_path = self.remote_jobfile_path

            # Record paths of remote log files for access by gcylc
            if True:
                # by ssh URL
                url_prefix = self.task_owner + '@' + self.remote_host
                self.logfiles.add_path( url_prefix + ':' + self.stdout_file)
                self.logfiles.add_path( url_prefix + ':' + self.stderr_file)
            else:
                # CURRENTLY DISABLED:
                # If the remote and suite hosts see a common filesystem, or
                # if the remote task is really just a local task with a
                # different owner, we could just use local filesystem access.
                # But to use this: (a) special namespace config would be
                # required to indicate we have a common filesystem, and
                # (b) we'd need to consider how the log directory can be
                # specified (for example use of '$HOME' as for remote
                # task use would not work here as log file access is by
                # gcylc under the suite owner account.
                self.logfiles.add_path( self.stdout_file )
                self.logfiles.add_path( self.stderr_file )
        else:
            # LOCAL TASKS
            self.local = True
            self.task_owner = self.suite_owner
            # Used in command construction:
            self.jobfile_path = self.local_jobfile_path

            # Local stdout and stderr log file paths:
            self.stdout_file = self.local_jobfile_path + ".out"
            self.stderr_file = self.local_jobfile_path + ".err"

            # Record paths of local log files for access by gcylc
            self.logfiles.add_path( self.stdout_file)
            self.logfiles.add_path( self.stderr_file)

        # Overrideable methods
        self.set_directives()
        self.set_scripting()
        self.set_environment()

    def set_directives( self ):
        # OVERRIDE IN DERIVED JOB SUBMISSION CLASSES THAT USE DIRECTIVES
        # (directives will be ignored if the prefix below is not overridden)

        # Prefix, e.g. '#QSUB' (qsub), or '# @' (loadleveler)
        self.directive_prefix = None
        # Final directive, WITH PREFIX, e.g. '# @ queue' for loadleveler
        self.final_directive = "# FINAL_DIRECTIVE"
        # Connector, e.g. ' = ' for loadleveler, ' ' for qsub
        self.directive_connector = " DIRECTIVE_CONNECTOR "

    def set_scripting( self ):
        # Derived class can use this to modify pre- and post-command scripting
        return

    def set_environment( self ):
        # Derived classes can use this to modify task execution environment
        return

    def construct_jobfile_submission_command( self ):
        # DERIVED CLASSES MUST OVERRIDE THIS METHOD to construct
        # self.command, the command to submit the job script to
        # run by the derived class job submission method.
        raise SystemExit( 'ERROR: no job submission command defined!' )

    def submit( self, dry_run ):
        try:
            os.chdir( pwd.getpwnam(self.suite_owner).pw_dir )
        except OSError, e:
            print >> sys.stderr, "Failed to change to suite owner's home directory"
            print >> sys.stderr, e
            return False

        jf = jobfile( self.task_id,
                self.__class__.cylc_env, self.task_env,
                self.namespace_hierarchy, self.directive_prefix,
                self.directive_connector, self.directives,
                self.final_directive, self.manual_messaging,
                self.initial_scripting, self.pre_command,
                self.task_command, self.try_number, self.post_command,
                self.remote_cylc_dir, self.remote_suite_dir,
                self.job_submission_shell, self.share_dir,
                self.work_dir, self.jobfile_path,
                self.__class__.simulation_mode, self.__class__.__name__ )
        # write the job file
        jf.write( self.local_jobfile_path )
        # make it executable
        os.chmod( self.local_jobfile_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

        # this is needed by the 'cylc jobscript' command:
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
            return None

        if not self.local:
            # direct the local jobfile across the ssh tunnel via stdin
            command = command + ' < ' + self.local_jobfile_path
        print command

        try:
            popen = subprocess.Popen( command, shell=True )
            # To test sequential job submission (pre cylc-4.5.1)
            # uncomment the following line (this tie cylc up for a while
            # in the event of submitting many ensemble tasks at once):
            ###popen.wait()
        except OSError, e:
            print >> sys.stderr, "ERROR: Job submission failed", e
            popen = None
        return popen


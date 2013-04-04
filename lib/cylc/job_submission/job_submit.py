#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

Writes a temporary "job file" that encapsulates the task runtime settings 
(execution environment, command scripting, etc.) then submits it by the 
chosen method on the chosen host (using passwordless ssh if not local).

Derived classes define the particular job submission method.
"""

import pwd, sys, os
import stat
from jobfile import jobfile
import socket
from subprocess import Popen, PIPE
from cylc.owner import user, is_remote_user
from cylc.suite_host import is_remote_host
from cylc.TaskID import TaskID

class job_submit(object):
    LOCAL_COMMAND_TEMPLATE = "%(jobfile_path)s --write-suite-env && %(command)s"
    REMOTE_COMMAND_TEMPLATE = ( " '"
            + "test -f /etc/profile && . /etc/profile 1>/dev/null 2>&1;"
            + "test -f $HOME/.profile && . $HOME/.profile 1>/dev/null 2>&1;"
            + " mkdir -p $(dirname %(jobfile_path)s)"
            + " && cat >%(jobfile_path)s"
            + " && chmod +x %(jobfile_path)s"
            + " && %(jobfile_path)s --write-suite-env"
            + " && (%(command)s)"
            + "'" )

    def __init__( self, task_id, jobconfig, xconfig, submit_num ):

        self.jobconfig = jobconfig

        self.task_id = task_id
        self.logfiles = xconfig['extra log files']

        self.job_submit_command_template = xconfig['job submission command template']
        self.remote_shell_template = xconfig['remote shell template']

        # Local job script path: append submit number.
        # (used by both local and remote tasks)
        tag = task_id + TaskID.DELIM + submit_num
        self.local_jobfile_path = os.path.join( xconfig['log path'], tag )
        # The directory is created in config.py
        self.logfiles.add_path( self.local_jobfile_path )

        self.suite_owner = user

        remote_host = xconfig['host']
        task_owner = xconfig['owner']

        if is_remote_host(remote_host) or is_remote_user(task_owner):
            # REMOTE TASK OR USER ACCOUNT SPECIFIED FOR TASK - submit using ssh
            self.local = False
            if task_owner:
                self.task_owner = task_owner
            else:
                self.task_owner = self.suite_owner

            if remote_host:
                self.remote_host = remote_host
            else:
                self.remote_host = socket.gethostname()

            self.remote_jobfile_path = os.path.join( xconfig['remote log path'], tag )

            # Remote log files
            self.stdout_file = self.remote_jobfile_path + ".out"
            self.stderr_file = self.remote_jobfile_path + ".err"

            # Used in command construction:
            self.jobfile_path = self.remote_jobfile_path

            # Record paths of remote log files for access by gui
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
                # gui under the suite owner account.
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

            # Record paths of local log files for access by gui
            self.logfiles.add_path( self.stdout_file)
            self.logfiles.add_path( self.stderr_file)

        # Overrideable methods
        self.set_directives()
        self.set_scripting()
        self.set_environment()

    def set_directives( self ):
        pass
        # OVERRIDE IN DERIVED JOB SUBMISSION CLASSES THAT USE DIRECTIVES
        # (directives will be ignored if the prefix below is not overridden)

        # Defaults set in task.py:
        # self.jobconfig = { 
        #  PREFIX: e.g. '#QSUB' (qsub), or '# @' (loadleveler)
        #      'directive prefix' : None,
        #  FINAL directive, WITH PREFIX, e.g. '# @ queue' for loadleveler
        #      'directive final' : '# FINAL_DIRECTIVE '
        #  CONNECTOR, e.g. ' = ' for loadleveler, ' ' for qsub
        #      'directive connector' :  " DIRECTIVE_CONNECTOR "
        # }

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

    def submit( self, dry_run=False, debug=False ):
        """ submit the task and return the process ID of the job
        submission sub-process, or None if a failure occurs."""

        try:
            os.chdir( pwd.getpwnam(self.suite_owner).pw_dir )
        except OSError, e:
            if debug:
                raise
            print >> sys.stderr, "ERROR:", e
            print >> sys.stderr, "ERROR: Failed to change to suite owner's home directory"
            print >> sys.stderr, "Use --debug to abort cylc with an exception traceback."
            return None

        jf = jobfile(\
                self.jobfile_path,
                self.__class__.__name__,
                self.task_id,
                self.jobconfig )

        # write the job file
        jf.write( self.local_jobfile_path )
        # make it executable
        mode = ( os.stat(self.local_jobfile_path).st_mode |
                 stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH )
        os.chmod( self.local_jobfile_path, mode )

        # this is needed by the 'cylc jobscript' command:
        print "JOB SCRIPT: " + self.local_jobfile_path

        # Construct self.command, the command to submit the jobfile to run
        try:
            self.construct_jobfile_submission_command()
        except TypeError, x:
            if debug:
                raise
            print >> sys.stderr, "ERROR:", x
            print >> sys.stderr, "ERROR: Failed to construct job submission command"
            print >> sys.stderr, """  Possible cause: a command template that is not compatible with the
  job submission method in terms of the number of string substitutions.
  Use --debug to abort cylc with an exception traceback."""
            return None

        if self.local:
            command = self.LOCAL_COMMAND_TEMPLATE % {
                      "jobfile_path": self.jobfile_path, "command": self.command}
        else:
            command = self.REMOTE_COMMAND_TEMPLATE % {
                      "jobfile_path": self.jobfile_path, "command": self.command}
            destination = self.task_owner + "@" + self.remote_host
            command = self.remote_shell_template % destination + command
        # execute the local command to submit the job
        if dry_run:
            print "THIS IS A DRY RUN. HERE'S HOW I WOULD SUBMIT THE TASK:"
            print 'SUBMIT:', command
            return None

        if not self.local:
            # direct the local jobfile across the ssh tunnel via stdin
            command = command + ' < ' + self.local_jobfile_path
        print 'SUBMIT #' + \
                str(self.jobconfig['absolute submit number']) + '(' + \
                str(self.jobconfig['submission try number']) + ',' + \
                str( self.jobconfig['try number']) + '):', command
        try:
            popen = Popen( command, shell=True, stdout=PIPE, stderr=PIPE )
            # To test sequential job submission (pre cylc-4.5.1)
            # uncomment the following line (this tie cylc up for a while
            # in the event of submitting many ensemble tasks at once):
            ###popen.wait()
        except OSError, e:
            if debug:
                raise
            print >> sys.stderr, "ERROR:", e
            print >> sys.stderr, "ERROR: Job submission failed"
            print >> sys.stderr, "Use --debug to abort cylc with an exception traceback."
            popen = None

        return popen


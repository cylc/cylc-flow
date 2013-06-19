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

from job_submit import job_submit
from cylc.command_env import pr_scripting_sl

class background( job_submit ):
    """
    Background 'job submission' runs the task directly in the background
    (with '&') so that we can get the job PID (with $!) but then uses
    'wait' to prevent exit before the job is finished (which would be a
    problem for remote background jobs at sites that do not allow
    unattended jobs on login nodes):
      % ssh user@host 'job-script & echo $!; wait'
    (We have to override the general command templates to achieve this)."""

    LOCAL_COMMAND_TEMPLATE = ( "(%(command)s & echo $!; wait )" )

    REMOTE_COMMAND_TEMPLATE = ( " '"
            + pr_scripting_sl + "; "
            + " mkdir -p $(dirname %(jobfile_path)s)"
            + " && cat >%(jobfile_path)s"
            + " && chmod +x %(jobfile_path)s" 
            + " && ( (%(command)s) & echo $!; wait )"
            + "'" )
 
    COMMAND_TEMPLATE = "%s </dev/null 1>%s 2>%s"

    def construct_jobfile_submission_command( self ):
        """
        Construct a command to submit this job to run.
        """
        command_template = self.job_submit_command_template
        if not command_template:
            command_template = self.__class__.COMMAND_TEMPLATE
        self.command = command_template % ( self.jobfile_path,
                                            self.stdout_file,
                                            self.stderr_file )

    def get_id( self, out, err ):
        """
        Extract the job process ID from job submission command
        output. For background jobs the submission command simply
        echoes the process ID to stdout as described above.
        """
        return out.strip()

    def get_job_poll_command( self, pid ):
        """
        Given the job process ID, return a command string that uses
        'cylc get-task-status' (on the task host) to determine current
        job status:
           cylc get-job-status <QUEUED> <RUNNING>
        where:
            QUEUED  = true if job is waiting or running, else false
            RUNNING = true if job is running, else false

        WARNING: 'cylc get-task-status' prints a task status message -
        the final result - to stdout, so any stdout from scripting prior
        to the call must be dumped to /dev/null.
        """
        status_file = self.jobfile_path + ".status"
        cmd = ( "RUNNING=false; "
                + "ps " + pid + " >/dev/null; "
                + "[[ $? == 0 ]] && RUNNING=true; "
                + "cylc get-task-status " + status_file + " $RUNNING $RUNNING"  )
        return cmd

    def get_job_kill_command( self, pid ):
        """
        Given the job process ID, return a command to kill the job.
        """
        cmd = "kill -9 " + pid
        return cmd


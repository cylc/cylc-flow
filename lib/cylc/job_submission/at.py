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
import re

class at( job_submit ):
    """
    Submit the task job script to the simple 'at' scheduler. Note that
    (1) the 'atd' daemon service must be running; (2) the atq command
    does not report if the job is running or not.

    How to make tasks stays in the queue for a while:
    [runtime]
      [[MyTask]]
        [[[job submission]]]
           method = at
           command template = 'echo "%s 1>%s 2>%s" | at now + 2 minutes'
    """

    COMMAND_TEMPLATE = "echo \"%s 1>%s 2>%s\" | at now" # % ( jobfile-path, out, err )
    REC_ID = re.compile(r"\Ajob\s(?P<id>\S+)\sat")

    # atq properties:
    #   * stdout is "job-num date hour queue username", e.g.:
    #      1762 Wed May 15 00:20:00 2013 = hilary
    #   * queue is '=' if running
    #   

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
        Extract the job submit ID from job submission command
        output. The at scheduler prints the job ID to stderr.
        """
        for line in str(err).splitlines():
            match = self.REC_ID.match(line)
            if match:
                return match.group("id")

    def get_job_poll_command( self, jid ):
        """
        Given the job submit ID, return a command string that uses
        cylc-get-task-status to determine current job status:
           cylc-get-job-status <QUEUED> <RUNNING>
        where:
            QUEUED  = true if job is waiting or running, else false
            RUNNING = true if job is running, else false

        WARNING: cylc-get-task-status prints a task status message - the
        final result - to stdout, so any stdout from scripting prior to
        the call must be dumped to /dev/null.
        """
        status_file = self.jobfile_path + ".status"
        cmd = ( "RUNNING=false; QUEUED=false; "
                + "atq | grep " + jid + " >/dev/null; "
                + "[[ $? == 0 ]] && QUEUED=true;"
                + "atq | grep " + jid + " | grep = >/dev/null; "
                + "[[ $? == 0 ]] && RUNNING=true; "
                + "cylc-get-task-status " + status_file + " $QUEUED $RUNNING"  )
        return cmd

    def get_job_kill_command( self, jid ):
        """
        Given the job submit ID, return a command to kill the job.
        The atrm command removes waiting jobs from the queue but it
        does not kill jobs that are already running, so we have to
        determine the job process ID by searching in 'ps' output.
        """
        cmd = ( "RUNNING=false; QUEUED=false; "
                + "atq | grep " + jid + " >/dev/null; "
                + "[[ $? == 0 ]] && QUEUED=true;"
                + "atq | grep " + jid + " | grep = >/dev/null; "
                + "[[ $? == 0 ]] && RUNNING=true; "
                + "! $QUEUED && echo WARNING job not found && exit 0; "
                + "! $RUNNING && atrm " + jid + " && exit 0; "
                + "ps aux | grep " + self.jobfile_path + " | grep -v grep | awk \"{print \$2}\" | xargs kill -9" )
        return cmd


#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
import os
import re
from signal import SIGKILL
from subprocess import check_call, Popen, PIPE

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

    # N.B. The perl command ensures that the job script is executed in its own
    # process group, which allows the job script and its child processes to be
    # killed correctly.
    COMMAND_TEMPLATE = (
            "echo \"perl -e \\\"setpgrp(0,0);exec(@ARGV)\\\" %s 1>%s 2>%s\"" +
            " | at now") # % ( jobfile-path, out, err )
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

    def filter_output( self, out, err):
        """Filter the stdout/stderr output - suppress ID stderr message."""
        new_err = ""
        if err:
            for line in err.splitlines():
                if not self.REC_ID.match(line):
                    new_err += line + "\n"
        return out, new_err

    def get_id( self, out, err ):
        """
        Extract the job submit ID from job submission command
        output. The at scheduler prints the job ID to stderr.
        """
        for line in str(err).splitlines():
            match = self.REC_ID.match(line)
            if match:
                return match.group("id")

    def kill( self, jid, st_file ):
        """Kill the job."""
        if os.access(st_file, os.F_OK | os.R_OK):
            for line in open(st_file):
                if line.startswith("CYLC_JOB_PID="):
                    pid = line.strip().split("=", 1)[1]
                    os.killpg(int(pid), SIGKILL)
                    # Killing the process group should remove it from the queue
                    return
        check_call(["atrm", jid])

    def poll( self, jid ):
        """Return 0 if jid is in the queueing system, 1 otherwise."""
        proc = Popen(["atq"], stdout=PIPE)
        if proc.wait():
            return 1
        out, err = proc.communicate()
        # "atq" returns something like this:
        #     5347	2013-11-22 10:24 a daisy
        #     499	2013-12-22 16:26 a daisy
        # "jid" is in queue if it matches column 1 of a row.
        for line in out.splitlines():
            items = line.strip().split(None, 1)
            if items and items[0] == jid:
                return 0
        return 1

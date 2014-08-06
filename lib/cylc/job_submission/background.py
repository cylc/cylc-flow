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

from job_submit import JobSubmit
from cylc.command_env import pr_scripting_sl
import os
from signal import SIGKILL
from subprocess import Popen, PIPE

class background( JobSubmit ):
    """
    Background 'job submission' runs the task directly in the background
    (with '&') so that we can get the job PID (with $!) but then uses
    'wait' to prevent exit before the job is finished (which would be a
    problem for remote background jobs at sites that do not allow
    unattended jobs on login nodes):
      % ssh user@host 'job-script & echo $!; wait'
    (We have to override the general command templates to achieve this)."""

    LOCAL_COMMAND_TEMPLATE = ( "( %(command)s & echo $!; wait )" )

    REMOTE_COMMAND_TEMPLATE = (
        " '" +
        pr_scripting_sl +
        "; " +
        " mkdir -p %(jobfile_dir)s" +
        " && cat >%(jobfile_path)s.tmp" +
        " && mv %(jobfile_path)s.tmp %(jobfile_path)s" +
        " && chmod +x %(jobfile_path)s" +
        " && rm -f %(jobfile_path)s.status" +
        " && ( %(command)s & echo $!; wait )" +
        "'")

    # N.B. The perl command ensures that the job script is executed in its own
    # process group, which allows the job script and its child processes to be
    # killed correctly.
    COMMAND_TEMPLATE = ("perl -e \"setpgrp(0,0);exec(@ARGV)\" %s " +
                        "</dev/null 1>%s 2>%s")

    def construct_job_submit_command( self ):
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

    def kill( self, jid, st_file=None ):
        """Kill the job."""
        os.killpg(int(jid), SIGKILL)

    def poll( self, jid ):
        """Return 0 if jid is in the queueing system, 1 otherwise."""
        return Popen(["ps", jid], stdout=PIPE).wait()

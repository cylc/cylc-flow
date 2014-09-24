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
"""Implement background job submission."""

from cylc.job_submission.job_submit import JobSubmit
import os
import re
from subprocess import Popen, PIPE
import sys


class background(JobSubmit):
    """Background job submission.

    Runs the task in a background process. Uses 'wait' to prevent exit before
    the job is finished (which would be a problem for remote background jobs at
    sites that do not allow unattended jobs on login nodes).

    """

    IS_BG_SUBMIT = True
    REC_ID_FROM_OUT = re.compile(r"""\A(?P<id>\d+)\Z""")

    def get_id(self, out, err):
        """
        Extract the job process ID from job submission command
        output. For background jobs the submission command simply
        echoes the process ID to stdout as described above.
        """
        return out.strip()

    def kill(self, st_file):
        """Kill the job."""
        return self.kill_proc_group(st_file)

    @classmethod
    def poll(cls, jid):
        """Return True if jid is in the queueing system."""
        return Popen(["ps", jid], stdout=PIPE).wait() == 0

    @classmethod
    def submit(cls, job_file_path, _=None):
        """Submit "job_file_path"."""
        out_file = open(job_file_path + ".out", "wb")
        err_file = open(job_file_path + ".err", "wb")
        proc = Popen(
            [job_file_path], stdout=out_file, stderr=err_file,
            preexec_fn=os.setpgrp)
        # Send PID info back to suite
        sys.stdout.write("CYLC_JOB_SUBMIT_METHOD_ID=%s\n" % proc.pid)
        sys.stdout.flush()
        # Write PID info to status file
        job_status_file = open(job_file_path + ".status", "a")
        job_status_file.write("CYLC_JOB_SUBMIT_METHOD_ID=%s\n" % proc.pid)
        job_status_file.close()
        # Wait for job
        ret_code = proc.wait()
        out_file.close()
        err_file.close()
        return (ret_code, None, None)

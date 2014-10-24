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
"""Background job submission and manipulation."""

import os
import re
from subprocess import Popen
import sys
from cylc.batch_sys_manager import BATCH_SYS_MANAGER


class BgCommandHandler(object):
    """Background job submission and manipulation.

    Run a task job as a background process. Uses 'wait' to prevent exit before
    the job is finished (which would be a problem for remote background jobs at
    sites that do not allow unattended jobs on login nodes).

    """

    CAN_KILL_PROC_GROUP = True
    IS_BG_SUBMIT = True
    POLL_CMD_TMPL = "ps '%(job_id)s'"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"""\A(?P<id>\d+)\Z""")

    @classmethod
    def submit(cls, job_file_path):
        """Submit "job_file_path"."""
        out_file = open(job_file_path + ".out", "wb")
        err_file = open(job_file_path + ".err", "wb")
        proc = Popen(
            [job_file_path], stdout=out_file, stderr=err_file,
            preexec_fn=os.setpgrp)
        # Send PID info back to suite
        sys.stdout.write("%(pid)d\n%(key)s=%(pid)d\n" % {
            "key": BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID,
            "pid": proc.pid,
        })
        sys.stdout.flush()
        # Write PID info to status file
        job_status_file = open(job_file_path + ".status", "a")
        job_status_file.write("%s=%d\n" % (
            BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID, proc.pid))
        job_status_file.close()
        # Wait for job
        proc.communicate()
        out_file.close()
        err_file.close()
        return proc


BATCH_SYS_HANDLER = BgCommandHandler()

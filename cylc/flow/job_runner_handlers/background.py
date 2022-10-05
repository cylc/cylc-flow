# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Runs job scripts as Unix background processes.

.. cylc-scope:: flow.cylc[runtime][<namespace>]

If an :cylc:conf:`execution time limit` is specified for a task, its job will
be wrapped by the ``timeout`` command.

.. cylc-scope::

"""

import errno
import os
import re
from subprocess import Popen, STDOUT, DEVNULL


class BgCommandHandler:
    """Background job submission and manipulation.

    Run a task job as a nohup background process in its own process group.

    """

    SHOULD_KILL_PROC_GROUP = True
    POLL_CMD = "ps"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"""\A(?P<id>\d+)\Z""")

    @classmethod
    def submit(cls, job_file_path, submit_opts):
        """Submit "job_file_path"."""
        # Check access permission here because we are unable to check the
        # result of the nohup command.
        if not os.access(job_file_path, os.R_OK | os.X_OK):
            exc = OSError(
                errno.EACCES, os.strerror(errno.EACCES), job_file_path)
            return (1, None, str(exc))
        job_file_path_dir = os.path.dirname(job_file_path)
        if not os.access(job_file_path_dir, os.W_OK):
            exc = OSError(
                errno.EACCES, os.strerror(errno.EACCES), job_file_path_dir)
            return (1, None, str(exc))
        try:
            # Run command with "timeout" if execution time limit set
            execution_time_limit = submit_opts.get("execution_time_limit")
            timeout_str = ""
            if execution_time_limit:
                timeout_str = (
                    " timeout --signal=XCPU %d" % execution_time_limit)
            # This is essentially a double fork to ensure that the child
            # process can detach as a process group leader and not subjected to
            # SIGHUP from the current process.
            # TODO: close stdout? Maybe atexit?
            proc = Popen(  # nosec
                [
                    "nohup",
                    "bash",
                    "-c",
                    (r'''exec%s "$0" <'/dev/null' >"$0.out" 2>"$0.err"''' %
                     timeout_str),
                    job_file_path,
                ],
                env=submit_opts.get('env'),
                preexec_fn=os.setpgrp,
                stdin=DEVNULL,
                stdout=DEVNULL,
                stderr=STDOUT
            )
            # * the purpose of this call is to run user defined code
        except OSError as exc:
            # subprocess.Popen has a bad habit of not setting the
            # filename of the executable when it raises an OSError.
            if not exc.filename:
                exc.filename = "nohup"
            return (1, None, str(exc))
        else:
            return (0, "%d\n" % (proc.pid), None)


JOB_RUNNER_HANDLER = BgCommandHandler()

#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""SLURM job submission and manipulation.

Includes directive prefix workaround for heterogeneous job support. See also
slurm_packjob for older Slurm versions that use "packjob" instead of "hetjob".

"""

import re
import shlex


class SLURMHandler(object):
    """SLURM job submission and manipulation."""

    DIRECTIVE_PREFIX = "#SBATCH "
    KILL_CMD_TMPL = "scancel '%(job_id)s'"
    # N.B. The "squeue -j JOB_ID" command returns 1 if JOB_ID is no longer in
    # the system, so there is no need to filter its output.
    POLL_CMD = "squeue -h"
    REC_ID_FROM_SUBMIT_OUT = re.compile(
        r"\ASubmitted\sbatch\sjob\s(?P<id>\d+)")
    REC_ID_FROM_POLL_OUT = re.compile(r"^ *(?P<id>\d+)")
    SUBMIT_CMD_TMPL = "sbatch '%(job)s'"

    # Heterogeneous job support
    #  Match artificial directive prefix
    REC_HETJOB = re.compile(r"^hetjob_(\d+)_")
    #  Separator between het job directive sections
    SEP_HETJOB = "#SBATCH hetjob"

    @classmethod
    def filter_poll_output(cls, out, _):
        """Return True if job_id is in the queueing system."""
        # squeue -h -j JOB_ID when JOB_ID has stopped can either exit with
        # non-zero exit code or return blank text.
        return out.strip()

    @classmethod
    def filter_poll_many_output(cls, out):
        """Return list of job IDs extracted from job poll stdout.

        Needed to avoid the extension for heterogenous jobs ("+0", "+1" etc.)

        """
        job_ids = set()
        for line in out.splitlines():
            m = cls.REC_ID_FROM_POLL_OUT.match(line)
            if m:
                job_ids.add(m.group("id"))
        return list(job_ids)

    @classmethod
    def format_directives(cls, job_conf):
        """Format the job directives for a job file."""
        job_file_path = re.sub(r'\$HOME/', '', job_conf['job_file_path'])
        directives = job_conf['directives'].__class__()
        directives['--job-name'] = (
            job_conf['suite_name'] + '.' + job_conf['task_id'])
        directives['--output'] = job_file_path.replace('%', '%%') + ".out"
        directives['--error'] = job_file_path.replace('%', '%%') + ".err"
        if (job_conf["execution_time_limit"] and
                directives.get("--time") is None):
            directives["--time"] = "%d:%02d" % (
                job_conf["execution_time_limit"] / 60,
                job_conf["execution_time_limit"] % 60)
        for key, value in job_conf['directives'].items():
            directives[key] = value
        lines = []
        seen = set()
        for key, value in directives.items():
            m = cls.REC_HETJOB.match(key)
            if m:
                n = m.groups()[0]
                if n != "0" and n not in seen:
                    lines.append(cls.SEP_HETJOB)
                seen.add(n)
                newkey = cls.REC_HETJOB.sub('', key)
            else:
                newkey = key
            if value:
                lines.append("%s%s=%s" % (cls.DIRECTIVE_PREFIX, newkey, value))
            else:
                lines.append("%s%s" % (cls.DIRECTIVE_PREFIX, newkey))
        return lines

    @staticmethod
    def get_fail_signals(_):
        """Return a list of failure signal names to trap.

        Do not include SIGTERM trapping, as SLURM tries to kill the
        parent script directly with SIGTERM rather than the process
        group as a whole. In these circumstances, this signal does
        not get handled. Bash waits for the (unsignalled) child to
        complete. This does not apply to jobs with proper 'steps'
        (e.g. using srun within an sbatch script), which are properly
        signalled.

        XCPU isn't used by SLURM at the moment, but it's a valid way
        to manually signal jobs using scancel or sbatch --signal.

        """
        return ["EXIT", "ERR", "XCPU"]

    @classmethod
    def get_poll_many_cmd(cls, job_ids):
        """Return the poll command for a list of job IDs."""
        return shlex.split(cls.POLL_CMD) + ["-j", ",".join(job_ids)]


BATCH_SYS_HANDLER = SLURMHandler()

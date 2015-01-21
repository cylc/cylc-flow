#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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
"""SLURM job submission and manipulation."""

import re


class SLURMHandler(object):
    """SLURM job submission and manipulation."""

    DIRECTIVE_PREFIX = "#SBATCH "
    KILL_CMD_TMPL = "scancel '%(job_id)s'"
    # N.B. The "squeue -j JOB_ID" command returns 1 if JOB_ID is no longer in
    # the system, so there is no need to filter its output.
    POLL_CMD_TMPL = "squeue -j '%(job_id)s'"
    REC_ID_FROM_SUBMIT_OUT = re.compile(
        r"\ASubmitted\sbatch\sjob\s(?P<id>\d+)")
    SUBMIT_CMD_TMPL = "sbatch '%(job)s'"

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = re.sub(r'\$HOME/', '', job_conf['job file path'])
        directives = job_conf['directives'].__class__()
        directives['--job-name'] = (
            job_conf['suite name'] + '.' + job_conf['task id'])
        directives['--output'] = job_file_path + ".out"
        directives['--error'] = job_file_path + ".err"
        directives.update(job_conf['directives'])
        lines = []
        for key, value in directives.items():
            if value:
                lines.append("%s%s=%s" % (self.DIRECTIVE_PREFIX, key, value))
            else:
                lines.append("%s%s" % (self.DIRECTIVE_PREFIX, key))
        return lines

    def get_fail_signals(self, job_conf):
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


BATCH_SYS_HANDLER = SLURMHandler()

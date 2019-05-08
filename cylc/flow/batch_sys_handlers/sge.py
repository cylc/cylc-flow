#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""SGE qsub job submission"""

import re


class SGEHandler(object):

    """SGE qsub job submission"""

    DIRECTIVE_PREFIX = "#$ "
    KILL_CMD_TMPL = "qdel '%(job_id)s'"
    # N.B. The "qstat -j JOB_ID" command returns 1 if JOB_ID is no longer in
    # the system, so there is no need to filter its output.
    POLL_CMD = "qstat"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"\D+(?P<id>\d+)\D+")
    SUBMIT_CMD_TMPL = "qsub '%(job)s'"

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = re.sub(r'\$HOME/', '', job_conf['job_file_path'])
        directives = job_conf['directives'].__class__()
        directives['-N'] = job_conf['suite_name'] + '.' + job_conf['task_id']
        directives['-o'] = job_file_path + ".out"
        directives['-e'] = job_file_path + ".err"
        if (job_conf["execution_time_limit"] and
                directives.get("-l h_rt") is None):
            directives["-l h_rt"] = "%d:%02d:%02d" % (
                job_conf["execution_time_limit"] / 3600,
                (job_conf["execution_time_limit"] / 60) % 60,
                job_conf["execution_time_limit"] % 60)
        for key, value in list(job_conf['directives'].items()):
            directives[key] = value
        lines = []
        for key, value in directives.items():
            if value and " " in key:
                # E.g. -l h_rt=3:00:00
                lines.append("%s%s=%s" % (self.DIRECTIVE_PREFIX, key, value))
            elif value:
                # E.g. -q queue_name
                lines.append("%s%s %s" % (self.DIRECTIVE_PREFIX, key, value))
            else:
                # E.g. -V
                lines.append("%s%s" % (self.DIRECTIVE_PREFIX, key))
        return lines

    @classmethod
    def get_poll_many_cmd(cls, _):
        """Return poll command"""
        # No way to run POLL_CMD on specific job id(s). List all user's jobs.
        # batch_sys_manager._jobs_poll_batch_sys checks requested id in list.
        return [cls.POLL_CMD]


BATCH_SYS_HANDLER = SGEHandler()

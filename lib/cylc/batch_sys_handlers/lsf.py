#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
"IBM Platform LSF bsub job submission"

import re


class LSFHandler(object):
    "IBM Platform LSF bsub job submission"

    DIRECTIVE_PREFIX = "#BSUB "
    KILL_CMD_TMPL = "bkill '%(job_id)s'"
    POLL_CMD_TMPL = "bjobs -noheader '%(job_id)s'"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"^Job <(?P<id>\d+)>")
    SUBMIT_CMD_TMPL = "bsub"
    SUBMIT_CMD_STDIN_EXEC_TMPL = "cat '%(job)s'"

    @classmethod
    def filter_poll_output(cls, out, job_id):
        """Return True if job_id is in the queueing system."""
        entries = out.strip().split()
        return (len(entries) >= 3 and entries[0] == job_id and
                entries[2] != "DONE")

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = re.sub(r'\$HOME/', '', job_conf['job file path'])
        directives = job_conf['directives'].__class__()
        directives['-J'] = job_conf['suite name'] + '.' + job_conf['task id']
        directives['-o'] = job_file_path + ".out"
        directives['-e'] = job_file_path + ".err"
        directives.update(job_conf['directives'])
        lines = []
        for key, value in directives.items():
            if value:
                lines.append("%s%s %s" % (self.DIRECTIVE_PREFIX, key, value))
            else:
                lines.append("%s%s" % (self.DIRECTIVE_PREFIX, key))
        return lines

    def get_fail_signals(self, job_conf):
        """Return a list of failure signal names to trap."""
        return ["EXIT", "ERR", "XCPU", "TERM", "INT", "SIGUSR2"]


BATCH_SYS_HANDLER = LSFHandler()

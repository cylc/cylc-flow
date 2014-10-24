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
"SGE qsub job submission"

import re


class SGEHandler(object):

    "SGE qsub job submission"

    DIRECTIVE_PREFIX = "#$ "
    KILL_CMD_TMPL = "qdel '%(job_id)s'"
    # N.B. The "qstat -j JOB_ID" command returns 1 if JOB_ID is no longer in
    # the system, so there is no need to filter its output.
    POLL_CMD_TMPL = "qstat -j '%(job_id)s'"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"\D+(?P<id>\d+)\D+")
    SUBMIT_CMD_TMPL = "qsub '%(job)s'"

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = re.sub(r'\$HOME/', '', job_conf['job file path'])
        directives = job_conf['directives'].__class__()
        directives['-N'] = job_conf['suite name'] + '.' + job_conf['task id']
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


BATCH_SYS_HANDLER = SGEHandler()

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
from cylc.job_submission.job_submit import JobSubmit
from subprocess import Popen, PIPE


class sge(JobSubmit):

    "SGE qsub job submission"

    EXEC_KILL = "qdel"
    EXEC_SUBMIT = "qsub"
    REC_ID_FROM_OUT = re.compile(r"\D+(?P<id>\d+)\D+")

    def set_directives(self):
        self.jobconfig['directive prefix'] = "#$"
        self.jobconfig['directive final'] = None
        self.jobconfig['directive connector'] = " "

        defaults = {}
        defaults['-N'] = self.task_id
        # Replace literal '$HOME' in stdout and stderr file paths with ''
        # because environment variables are not interpreted in directives.
        # (For remote tasks the local home directory path is replaced
        # with '$HOME' in config.py).
        defaults['-o'] = re.sub('\$HOME/', '', self.stdout_file)
        defaults['-e'] = re.sub('\$HOME/', '', self.stderr_file)

        # In case the user wants to override the above defaults:
        for key, val in self.jobconfig['directives'].items():
            defaults[key] = val
        self.jobconfig['directives'] = defaults

    @classmethod
    def poll(cls, jid):
        """Return True if jid is in the queueing system."""
        return not Popen(["qstat", "-j", jid], stdout=PIPE).wait()

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
"Loadleveler job submission"

import re
from cylc.job_submission.job_submit import JobSubmit
import cylc.TaskID
from subprocess import Popen, PIPE


class loadleveler(JobSubmit):

    "Loadleveler job submission"

    EXEC_KILL = "llcancel"
    EXEC_SUBMIT = "llsubmit"
    REC_ID_FROM_OUT = re.compile(
        r"""\Allsubmit:\sThe\sjob\s"(?P<id>[^"]+)"\s""")
    REC_ERR_FILTERS = [
        re.compile("^llsubmit: Processed command file through Submit Filter:")]

    def set_directives(self):
        self.jobconfig['directive prefix'] = "# @"
        self.jobconfig['directive connector'] = " = "
        self.jobconfig['directive final'] = "# @ queue"

        defaults = {}
        defaults['job_name'] = self.suite + cylc.TaskID.DELIM + self.task_id
        # Replace literal '$HOME' in stdout and stderr file paths with ''
        # because environment variables are not interpreted in directives.
        # (For remote tasks the local home directory path is replaced
        # with '$HOME' in config.py).
        defaults['output'] = re.sub('\$HOME/', '', self.stdout_file)
        defaults['error'] = re.sub('\$HOME/', '', self.stderr_file)

        # NOTE ON SHELL DIRECTIVE: on AIX at NIWA '#@ shell = /bin/bash'
        # results in the job executing in a non-login shell (.profile
        # not sourced) whereas /bin/ksh does get a login shell. WTF?! In
        # any case this directive appears to affect only the shell *from
        # which the task job script is executed*, NOT the shell *in which it
        # is executed* (that is determined by the '#!' at the top of the
        # task job script).
        defaults['shell'] = '/bin/ksh'

        # NOTE if the initial "running dir" does not exist (or is not
        # writable by the user?) loadleveler will hold the job. Use
        # the 'initialdir' directive to fix this.

        # In case the user wants to override the above defaults:
        for key, val in self.jobconfig['directives'].items():
            defaults[key] = val
        self.jobconfig['directives'] = defaults

    def set_job_vacation_signal(self):
        """Set self.jobconfig['job vacation signal'] = 'USR1'

        (If restart=yes is defined in self.jobconfig['directives'])

        """
        if self.jobconfig['directives'].get('restart') == 'yes':
            self.jobconfig['job vacation signal'] = 'USR1'

    def filter_output(self, out, err):
        """Filter the stdout/stderr output - suppress process message."""
        new_err = ""
        if err:
            for line in err.splitlines():
                if any([rec.match(line) for rec in self.REC_ERR_FILTERS]):
                    continue
                new_err += line + "\n"
        return out, new_err

    @classmethod
    def poll(cls, jid):
        """Return True if jid is in the queueing system."""
        proc = Popen(["llq", "-f%id", jid], stdout=PIPE)
        if proc.wait():
            return False
        out = proc.communicate()[0]
        # "llq -f%id ID" returns EITHER something like:
        #     Step Id
        #     ------------------------
        #     a001.3274552.0
        #
        #     1 job step(s) in query, ...
        # OR:
        #     llq: There is currently no job status to report.
        # "jid" is in queue if it matches a stripped row.
        for line in out.splitlines():
            items = line.strip().split(None, 1)
            if items and (items[0] == jid or items[0].startswith(jid + ".")):
                return True
        return False

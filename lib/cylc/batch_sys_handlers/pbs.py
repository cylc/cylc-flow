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
"PBS batch system job submission and manipulation."

import re


class PBSHandler(object):

    "PBS batch system job submission and manipulation."

    DIRECTIVE_PREFIX = "#PBS "
    KILL_CMD_TMPL = "qdel '%(job_id)s'"
    # N.B. The "qstat JOB_ID" command returns 1 if JOB_ID is no longer in the
    # system, so there is no need to filter its output.
    POLL_CMD_TMPL = "qstat '%(job_id)s'"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"""\A\s*(?P<id>\S+)\s*\Z""")
    SUBMIT_CMD_TMPL = "qsub '%(job)s'"

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = job_conf["job file path"].replace(r"$HOME/", "")
        directives = job_conf["directives"].__class__()  # an ordereddict

        # Old versions of PBS (< 11) requires jobs names <= 15 characters.
        # Version 12 appears to truncate the job name to 15 characters if it is
        # longer.
        directives["-N"] = (
            job_conf["task id"] + "." + job_conf["suite name"])[0:15]

        directives["-o"] = job_file_path + ".out"
        directives["-e"] = job_file_path + ".err"
        directives.update(job_conf["directives"])
        lines = []
        for key, value in directives.items():
            if value and " " in key:
                # E.g. -l walltime=3:00:00
                lines.append("%s%s=%s" % (self.DIRECTIVE_PREFIX, key, value))
            elif value:
                # E.g. -q queue_name 
                lines.append("%s%s %s" % (self.DIRECTIVE_PREFIX, key, value))
            else:
                # E.g. -V 
                lines.append(self.DIRECTIVE_PREFIX + key)
        return lines


BATCH_SYS_HANDLER = PBSHandler()

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
"PBS batch system job submission and manipulation."

import re


class PBSHandler(object):

    "PBS batch system job submission and manipulation."

    DIRECTIVE_PREFIX = "#PBS "
    # PBS fails a job submit if job "name" in "-N name" is too long.
    # For version 12 or below, this is 15 characters.
    # You can modify this in the site/user `global.cfg` like this
    # [hosts]
    #     [[the-name-of-my-pbs-host]]
    #         [[[batch systems]]]
    #             [[[[pbs]]]]
    #                # E.g.: PBS 13
    #                job name length maximum = 236
    JOB_NAME_LEN_MAX = 15
    KILL_CMD_TMPL = "qdel '%(job_id)s'"
    # N.B. The "qstat JOB_ID" command returns 1 if JOB_ID is no longer in the
    # system, so there is no need to filter its output.
    POLL_CMD = "qstat"
    POLL_CANT_CONNECT_ERR = "cannot connect to server"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"""\A\s*(?P<id>\S+)\s*\Z""")
    SUBMIT_CMD_TMPL = "qsub '%(job)s'"

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = job_conf["job_file_path"].replace(r"$HOME/", "")
        directives = job_conf["directives"].__class__()  # an ordereddict

        directives["-N"] = job_conf["task_id"] + "." + job_conf["suite_name"]
        job_name_len_max = job_conf['batch_system_conf'].get(
            "job name length maximum", self.JOB_NAME_LEN_MAX)
        if job_name_len_max:
            directives["-N"] = directives["-N"][0:job_name_len_max]

        directives["-o"] = job_file_path + ".out"
        directives["-e"] = job_file_path + ".err"
        if (job_conf["execution_time_limit"] and
                directives.get("-l walltime") is None):
            directives["-l walltime"] = "%d" % job_conf["execution_time_limit"]
        for key, value in job_conf["directives"].items():
            directives[key] = value
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

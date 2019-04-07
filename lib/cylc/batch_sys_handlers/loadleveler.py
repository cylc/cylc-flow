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
"""Loadleveler job submission"""

import re


class LoadlevelerHandler(object):

    """Loadleveler job submission"""

    DIRECTIVE_PREFIX = "# @ "
    KILL_CMD_TMPL = "llcancel '%(job_id)s'"
    POLL_CMD = "llq"
    REC_ID_FROM_SUBMIT_OUT = re.compile(
        r"""\Allsubmit:\sThe\sjob\s"(?P<id>[^"]+)"\s""")
    REC_ERR_FILTERS = [
        re.compile("^llsubmit: Processed command file through Submit Filter:")]
    SUBMIT_CMD_TMPL = "llsubmit '%(job)s'"
    VACATION_SIGNAL = "USR1"

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = re.sub(r"\$HOME/", "", job_conf["job_file_path"])
        directives = job_conf["directives"].__class__()
        directives["job_name"] = (
            job_conf["suite_name"] + "." + job_conf["task_id"])
        directives["output"] = job_file_path + ".out"
        directives["error"] = job_file_path + ".err"
        if (job_conf["execution_time_limit"] and
                directives.get("wall_clock_limit") is None):
            directives["wall_clock_limit"] = "%d,%d" % (
                job_conf["execution_time_limit"] + 60,
                job_conf["execution_time_limit"])
        for key, value in list(job_conf["directives"].items()):
            directives[key] = value
        lines = []
        for key, value in directives.items():
            if value:
                lines.append("%s%s = %s" % (self.DIRECTIVE_PREFIX, key, value))
            else:
                lines.append("%s%s" % (self.DIRECTIVE_PREFIX, key))
        lines.append("%squeue" % (self.DIRECTIVE_PREFIX))
        return lines

    def filter_submit_output(self, out, err):
        """Filter the stdout/stderr output - suppress process message."""
        new_err = ""
        if err:
            for line in err.splitlines():
                if any(rec.match(line) for rec in self.REC_ERR_FILTERS):
                    continue
                new_err += line + "\n"
        return out, new_err

    @classmethod
    def filter_poll_output(cls, out, job_id):
        """Return True if job_id is in the queueing system."""
        # "llq -f%id JOB_ID" returns 0 whether JOB_ID is in the system or not.
        # Therefore, we need to parse its output.
        # "llq -f%id JOB_ID" returns EITHER something like:
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
            if (items and
                    (items[0] == job_id or items[0].startswith(job_id + "."))):
                return True
        return False

    @classmethod
    def filter_poll_many_output(cls, out):
        """Return a list of job IDs still in the batch system.

        Drop STEPID from the JOBID.STEPID returned by 'llq'.
        """
        job_ids = []
        for line in out.splitlines():
            try:
                head = line.split(None, 1)[0]
            except IndexError:
                continue
            job_ids.append(".".join(head.split(".")[:2]))
        return job_ids

    def get_vacation_signal(self, job_conf):
        """Return "USR1" if "restart" directive is "yes"."""
        if job_conf["directives"].get("restart") == "yes":
            return self.VACATION_SIGNAL


BATCH_SYS_HANDLER = LoadlevelerHandler()

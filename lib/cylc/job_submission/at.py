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
"""Implement "at now" job submission."""

from cylc.job_submission.job_submit import JobSubmit
import re
from subprocess import Popen, PIPE


class at(JobSubmit):
    """
    Submit the task job script to the simple 'at' scheduler. Note that
    (1) the 'atd' daemon service must be running; (2) the atq command
    does not report if the job is running or not.

    How to make tasks stays in the queue for a while:
    [runtime]
      [[MyTask]]
        [[[job submission]]]
           method = at
           command template = 'echo "%s 1>%s 2>%s" | at now + 2 minutes'
    """

    # N.B. The perl command ensures that the job script is executed in its own
    # process group, which allows the job script and its child processes to be
    # killed correctly.
    COMMAND_TEMPLATE = (
        "echo \"perl -e 'setpgrp(0,0);exec(@ARGV)'" +
        " '%(job)s' 1>'%(job)s.out' 2>'%(job)s.err'\" | at now")
    REC_ERR_FILTERS = [
        re.compile("warning: commands will be executed using /bin/sh")]
    EXEC_KILL = "atrm"
    REC_ID_FROM_ERR = re.compile(r"\Ajob\s(?P<id>\S+)\sat")

    # atq properties:
    #   * stdout is "job-num date hour queue username", e.g.:
    #      1762 Wed May 15 00:20:00 2013 = hilary
    #   * queue is '=' if running
    #

    def filter_output(self, out, err):
        """Suppress at's routine output to stderr.

        Otherwises we get warning messages that suggest something is wrong.
        1) move the standard job ID message from stderr to stdout
        2) suppress the message warning that commands will be executed with
        /bin/sh (this refers to the command line that runs the job script).

        Call get_id() first, to extract the job ID.

        """

        if out is not None:
            out_lines = out.split()
        else:
            out_lines = []
        new_err = ""
        new_out = ""
        if err:
            for line in err.splitlines():
                if self.REC_ID_FROM_ERR.match(line):
                    out_lines.append(line)
                elif any([rec.match(line) for rec in self.REC_ERR_FILTERS]):
                    continue
                else:
                    new_err += line + "\n"
        new_out = "\n".join(out_lines)
        return new_out, new_err

    def kill(self, st_file):
        """Kill the job."""
        if self.kill_proc_group(st_file):  # return 1
            JobSubmit.kill(self, st_file)

    @classmethod
    def poll(cls, jid):
        """Return True if jid is in the queueing system."""
        proc = Popen(["atq"], stdout=PIPE)
        if proc.wait():
            return 1
        out = proc.communicate()[0]
        # "atq" returns something like this:
        #     5347	2013-11-22 10:24 a daisy
        #     499	2013-12-22 16:26 a daisy
        # "jid" is in queue if it matches column 1 of a row.
        for line in out.splitlines():
            items = line.strip().split(None, 1)
            if items and items[0] == jid:
                return True
        return False

    def submit(self, job_file_path, command_template=None):
        """Construct a command to submit this job to run."""

        if not command_template:
            command_template = self.COMMAND_TEMPLATE
        command = command_template % {"job": job_file_path}
        proc = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
        out, err = proc.communicate()
        return (proc.wait(), out, err)

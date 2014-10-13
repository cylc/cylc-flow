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
"""Logic to submit jobs to the "at" batch system."""

import re
from subprocess import Popen, PIPE


class AtCommandHandler(object):
    """Logic to submit jobs to the "at" batch system.

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

    CAN_KILL_PROC_GROUP = True
    # N.B. The perl command ensures that the job script is executed in its own
    # process group, which allows the job script and its child processes to be
    # killed correctly.
    KILL_CMD = "atrm"
    POLL_CMD = "atq"
    REC_ERR_FILTERS = [
        re.compile("warning: commands will be executed using /bin/sh")]
    REC_ID_FROM_SUBMIT_ERR = re.compile(r"\Ajob\s(?P<id>\S+)\sat")
    _CMD_TMPL = (
        r"exec perl -e 'setpgrp(0,0);exec(@ARGV)'" +
        r" '%(job)s' 1>'%(job)s.out' 2>'%(job)s.err'")

    # atq properties:
    #   * stdout is "job-num date hour queue username", e.g.:
    #      1762 Wed May 15 00:20:00 2013 = hilary
    #   * queue is '=' if running
    #

    def filter_submit_output(self, out, err):
        """Suppress at's routine output to stderr.

        Otherwises we get warning messages that suggest something is wrong.
        1) move the standard job ID message from stderr to stdout
        2) suppress the message warning that commands will be executed with
        /bin/sh (this refers to the command line that runs the job script).

        Call get_id() first, to extract the job ID.

        """

        new_err = ""
        if err:
            for line in err.splitlines(True):
                if self.REC_ID_FROM_SUBMIT_ERR.match(line):
                    out += line
                elif any([rec.match(line) for rec in self.REC_ERR_FILTERS]):
                    continue
                else:
                    new_err += line
        return out, new_err

    @classmethod
    def filter_poll_output(cls, out, job_id):
        """Return True if job_id is in the queueing system."""
        # "atq" returns something like this:
        #     5347	2013-11-22 10:24 a daisy
        #     499	2013-12-22 16:26 a daisy
        # "jid" is in queue if it matches column 1 of a row.
        for line in out.splitlines():
            items = line.strip().split(None, 1)
            if items and items[0] == job_id:
                return True
        return False

    def submit(self, job_file_path):
        """Run the "job_file_path" with "at now"."""
        proc = Popen(["at", "now"], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        proc.stdin.write(self._CMD_TMPL % {"job": job_file_path})
        return proc


BATCH_SYS_HANDLER = AtCommandHandler()

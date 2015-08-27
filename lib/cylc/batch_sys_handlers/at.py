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
"""Logic to submit jobs to the "at" batch system."""

import errno
import os
import re


class AtCommandHandler(object):
    """Logic to submit jobs to the "at" batch system.

    Submit the task job script to the simple 'at' scheduler. Note that
    (1) the 'atd' daemon service must be running; (2) the atq command
    does not report if the job is running or not.

    How to make tasks stays in the queue until tea time:
    [runtime]
      [[MyTask]]
        [[[job submission]]]
           method = at
           command template = at teatime
    """

    ERR_NO_ATD = "Can't open /var/run/atd.pid to signal atd. No atd running?"
    CAN_KILL_PROC_GROUP = True
    # N.B. The perl command ensures that the job script is executed in its own
    # process group, which allows the job script and its child processes to be
    # killed correctly.
    KILL_CMD_TMPL = "atrm '%(job_id)s'"
    POLL_CMD = "atq"
    POLL_CMD_TMPL = POLL_CMD
    REC_ERR_FILTERS = [
        re.compile("warning: commands will be executed using /bin/sh")]
    REC_ID_FROM_SUBMIT_ERR = re.compile(r"\Ajob\s(?P<id>\S+)\sat")
    SUBMIT_CMD_TMPL = "at now"
    SUBMIT_CMD_STDIN_TMPL = (
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
                elif line.strip() == self.ERR_NO_ATD:
                    raise OSError(
                        errno.ESRCH, os.strerror(errno.ESRCH), line)
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


BATCH_SYS_HANDLER = AtCommandHandler()

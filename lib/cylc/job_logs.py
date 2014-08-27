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
"""Logging of output from job activities."""

import os
import logging

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.mkdir_p import mkdir_p
from cylc.wallclock import get_current_time_string


class CommandLogger(object):
    """Log daemon-invoked command output to the job log dir."""

    LOGGING_PRIORITY = {
        "INFO": logging.INFO,
        "NORMAL": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "DEBUG": logging.DEBUG,
    }

    # Format string for single line output
    JOB_LOG_FMT_1 = "%(timestamp)s %(mesg_type)s: %(mesg)s"
    # Format string for multi-line output
    JOB_LOG_FMT_M = "%(timestamp)s %(mesg_type)s:\n\n%(mesg)s\n"

    @classmethod
    def get_create_job_log_path(cls, suite, task_name, task_point, submit_num):
        """Return a new job log path on the suite host, in two parts.

        /part1/part2

        * part1: the top level job log directory on the suite host.
        * part2: the rest, which is also used on remote task hosts.

        The full local job log directory is created if necessary, and its
        parent symlinked to NN (submit number).

        """

        suite_job_log_dir = GLOBAL_CFG.get_derived_host_item(
            suite, "suite job log directory")

        the_rest_dir = os.path.join(
            str(task_point), task_name, "%02d" % int(submit_num))
        the_rest = os.path.join(the_rest_dir, "job")

        local_log_dir = os.path.join(suite_job_log_dir, the_rest_dir)

        mkdir_p(local_log_dir)
        target = os.path.join(os.path.dirname(local_log_dir), "NN")
        try:
            os.unlink(target)
        except OSError:
            pass
        try:
            os.symlink(os.path.basename(local_log_dir), target)
        except OSError as exc:
            if not exc.filename:
                exc.filename = target
            raise exc
        return suite_job_log_dir, the_rest

    def __init__(self, suite, task_name, task_point):
        dir_ = GLOBAL_CFG.get_derived_host_item(
            suite, "suite job log directory")
        self.base_path = os.path.join(dir_, str(task_point), task_name)
        self.suite_logger = logging.getLogger("main")

    def append_to_log(self, submit_num, log_type, out=None, err=None):
        """Write new command output to the appropriate log file."""
        sub_num = "%02d" % int(submit_num)
        dir_ = os.path.join(self.base_path, sub_num)
        mkdir_p(dir_)
        job_log_handle = open(os.path.join(dir_, "job-activity.log"), "a")
        timestamp = get_current_time_string()
        self._write_to_log(job_log_handle, timestamp, log_type + "-OUT", out)
        self._write_to_log(job_log_handle, timestamp, log_type + "-ERR", err)
        job_log_handle.close()

    def _write_to_log(self, job_log_handle, timestamp, mesg_type, mesg):
        """Write message to the logs."""
        if mesg:
            if mesg_type.endswith("-ERR"):
                self.suite_logger.warning(mesg)
            else:
                self.suite_logger.info(mesg)
            if len(mesg.splitlines()) > 1:
                fmt = self.JOB_LOG_FMT_M
            else:
                fmt = self.JOB_LOG_FMT_1
            if not mesg.endswith("\n"):
                mesg += "\n"
            job_log_handle.write(fmt % {
                "timestamp": timestamp,
                "mesg_type": mesg_type,
                "mesg": mesg})

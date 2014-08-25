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

import os
import sys
import logging

from cfgspec.site import sitecfg
from mkdir_p import mkdir_p
from wallclock import get_current_time_string

job_log = "job"

command_logs = {
        "SUBMIT" : "job-submit",
        "EVENT" : "job-event",
        "POLL" : "job-poll",
        "KILL" : "job-kill",
}

logging_priority = {
        'INFO' : logging.INFO,
        'NORMAL' : logging.INFO,
        'WARNING' : logging.WARNING,
        'ERROR' : logging.ERROR,
        'CRITICAL' : logging.CRITICAL,
        'DEBUG' : logging.DEBUG
}


def get_create_job_log_path(suite, task_name, task_point, submit_num):
    """Return a new job log path on the suite host, in two parts.
    
    /part1/part2
    
    * part1: the top level job log directory on the suite host.
    * part2: the rest, which is also used on remote task hosts.
    
    The full local job log directory is created if necessary, and its parent
    symlinked to NN (submit number).

    """

    suite_job_log_dir = sitecfg.get_derived_host_item(
            suite, "suite job log directory")

    the_rest_dir = os.path.join(
            str(task_point), task_name, "%02d" % int(submit_num))
    the_rest = os.path.join(the_rest_dir, job_log)

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


class CommandLogger(object):
    """Log daemon-invoked command output to the job log dir."""

    def __init__(self, suite, task_name, task_point):
        dir = sitecfg.get_derived_host_item(
                suite, "suite job log directory")
        self.base_path = os.path.join(
                dir, str(task_point), task_name)
        self.suite_logger = logging.getLogger("main")

    def append_to_log(self, submit_num, type, out=None, err=None):
        """Write new command output to the appropriate log file."""

        if type not in command_logs:
            print sys.stderr, (
                    "WARNING: using non-standard command log: %s" % type)
            ftype = type
        else:
            ftype = command_logs[type]
        sub_num = "%02d" % int(submit_num)
        dir = os.path.join(self.base_path,sub_num)
        mkdir_p(dir)
        fbase = os.path.join(dir, ftype)
        timestamp = '[%s]' % get_current_time_string()
        if out:
            if not out.endswith('\n'):
                out += '\n'
            self.suite_logger.info(out)
            with open(fbase + ".out", 'a') as f:
               f.write("%s %s" % (timestamp, out))
        if err:
            if not err.endswith('\n'):
                err += '\n'
            self.suite_logger.warning(err)
            with open(fbase + ".err", 'a') as f:
                f.write("%s %s" % (timestamp, err))

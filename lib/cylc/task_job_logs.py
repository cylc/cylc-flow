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
"""Define task job log filenames and option names."""

import os
from cylc.cfgspec.glbl_cfg import glbl_cfg

# Task job log filenames.
JOB_LOG_JOB = "job"
JOB_LOG_OUT = "job.out"
JOB_LOG_ERR = "job.err"
JOB_LOG_ACTIVITY = "job-activity.log"
JOB_LOG_STATUS = "job.status"
JOB_LOG_XTRACE = "job.xtrace"  # Note this is also defined in job.sh.
JOB_LOG_DIFF = "job-edit.diff"

JOB_LOG_OPTS = {
    'j': JOB_LOG_JOB,
    'o': JOB_LOG_OUT,
    'e': JOB_LOG_ERR,
    'a': JOB_LOG_ACTIVITY,
    's': JOB_LOG_STATUS,
    'x': JOB_LOG_XTRACE,
    'd': JOB_LOG_DIFF
}

JOB_LOGS_LOCAL = [JOB_LOG_ACTIVITY, JOB_LOG_DIFF]

NN = "NN"


def get_task_job_id(point, name, submit_num=None):
    """Return the job log path from cycle point down."""
    try:
        submit_num = "%02d" % submit_num
    except TypeError:
        submit_num = NN
    return os.path.join(str(point), name, submit_num)


def get_task_job_log(suite, point, name, submit_num=None, suffix=None):
    """Return the full job log path."""
    args = [
        glbl_cfg().get_derived_host_item(suite, "suite job log directory"),
        get_task_job_id(point, name, submit_num)]
    if suffix is not None:
        args.append(suffix)
    return os.path.join(*args)


def get_task_job_activity_log(suite, point, name, submit_num=None):
    """Shorthand for get_task_job_log(..., suffix="job-activity.log")."""
    return get_task_job_log(suite, point, name, submit_num, JOB_LOG_ACTIVITY)


def get_task_job_job_log(suite, point, name, submit_num=None):
    """Shorthand for get_task_job_log(..., suffix="job")."""
    return get_task_job_log(suite, point, name, submit_num, JOB_LOG_JOB)

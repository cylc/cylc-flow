# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
"""Define job log filenames and option names."""

import os

from cylc.flow.id import Tokens
from cylc.flow.pathutil import get_workflow_run_job_dir

# job log filenames.
JOB_LOG_JOB = "job"
JOB_LOG_OUT = "job.out"
JOB_LOG_ERR = "job.err"
JOB_LOG_ACTIVITY = "job-activity.log"
JOB_LOG_STATUS = "job.status"
JOB_LOG_XTRACE = "job.xtrace"  # Note this is also defined in job.sh.

JOB_LOG_OPTS = {
    'j': JOB_LOG_JOB,
    'o': JOB_LOG_OUT,
    'e': JOB_LOG_ERR,
    'a': JOB_LOG_ACTIVITY,
    's': JOB_LOG_STATUS,
    'x': JOB_LOG_XTRACE,
}

NN = "NN"


def get_task_job_log(workflow, point, name, submit_num=None, suffix=None):
    """Return the full job log path."""
    args = [
        get_workflow_run_job_dir(workflow),
        Tokens(
            cycle=str(point),
            task=name,
            job=str(submit_num or NN),
        ).relative_id
    ]
    if suffix is not None:
        args.append(suffix)
    return os.path.join(*args)


def get_task_job_activity_log(workflow, point, name, submit_num=None):
    """Shorthand for get_task_job_log(..., suffix="job-activity.log")."""
    return get_task_job_log(
        workflow, point, name, submit_num, JOB_LOG_ACTIVITY)


def get_task_job_job_log(workflow, point, name, submit_num=None):
    """Shorthand for get_task_job_log(..., suffix="job")."""
    return get_task_job_log(workflow, point, name, submit_num, JOB_LOG_JOB)

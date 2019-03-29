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
"""Manage the job pool of a suite.

At present this pool represents a pseudo separation of task proxies and
their jobs, and is feed-to/used-by the UI Server in resolving queries.

"""
from time import time

from cylc.flow.task_id import TaskID
from cylc.flow.task_state import (
    TASK_STATUS_READY, TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED)
from cylc.flow.ws_messages_pb2 import PbJob

JOB_STATUSES_ALL = [
    TASK_STATUS_READY,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
]


class JobPool(object):
    """Pool of protobuf job messages."""
    # TODO: description, args, and types

    ERR_PREFIX_JOBID_MATCH = "No matching jobs found: "
    ERR_PREFIX_JOB_NOT_ON_SEQUENCE = "Invalid cycle point for job: "

    def __init__(self, suite, owner):
        self.suite = suite
        self.owner = owner
        self.pool = {}

    def insert_job(self, job_conf):
        """Insert job into pool."""
        update_time = time()
        int_id = job_conf['job_d']
        job_owner = job_conf['owner']
        name, point_string = TaskID.split(job_conf['task_id'])
        t_id = f"{self.owner}/{self.suite}/{point_string}/{name}"
        j_id = f"{self.owner}/{self.suite}/{int_id}"
        j_buf = PbJob(
            checksum=f"{int_id}@{update_time}",
            id=j_id,
            submit_num=job_conf['submit_num'],
            state=JOB_STATUSES_ALL[0],
            task_proxy=t_id,
            batch_sys_name=job_conf['batch_system_name'],
            env_script=job_conf['env-script'],
            err_script=job_conf['err-script'],
            exit_script=job_conf['exit-script'],
            execution_time_limit=job_conf['execution_time_limit'],
            host=job_conf['host'],
            init_script=job_conf['init-script'],
            job_log_dir=job_conf['job_log_dir'],
            owner=job_owner,
            post_script=job_conf['post-script'],
            pre_script=job_conf['pre-script'],
            script=job_conf['script'],
            work_sub_dir=job_conf['work_d'],
        )
        j_buf.batch_sys_conf.extend(
            [f"{key}={val}" for key, val in
                job_conf['batch_system_conf'].items()])
        j_buf.directives.extend(
            [f"{key}={val}" for key, val in
                job_conf['directives'].items()])
        j_buf.environment.extend(
            [f"{key}={val}" for key, val in
                job_conf['environment'].items()])
        j_buf.param_env_tmpl.extend(
            [f"{key}={val}" for key, val in
                job_conf['param_env_tmpl'].items()])
        j_buf.param_var.extend(
            [f"{key}={val}" for key, val in
                job_conf['param_var'].items()])
        j_buf.extra_logs.extend(job_conf['logfiles'])
        self.pool[int_id] = j_buf

    def remove_job(self, job_d):
        """Remove job from pool."""
        try:
            del self.pool[job_d]
        except KeyError:
            pass

    def remove_task_jobs(self, task_id):
        """removed all jobs associated with a task from the pool."""
        name, point_string = TaskID.split(task_id)
        t_id = f"/{point_string}/{name}/"
        for job_d in self.pool.keys():
            if t_id in job_d:
                del self.pool[job_d]

    def set_job_attr(self, job_d, attr_key, attr_val):
        """Set job attribute."""
        try:
            setattr(self.pool[job_d], attr_key, attr_val)
        except (KeyError, TypeError):
            pass

    def set_job_state(self, job_d, status):
        """Set job state."""
        if status in JOB_STATUSES_ALL:
            try:
                self.pool[job_d].state = status
            except KeyError:
                pass

    def set_job_time(self, job_d, event_key, time_str=None):
        """Set an event time in job pool object.

        Set values of both event_key + "_time" and event_key + "_time_string".
        """
        try:
            setattr(self.pool[job_d], event_key + '_time', time_str)
        except KeyError:
            pass

    @staticmethod
    def parse_job_item(item):
        """Parse point/name/submit_num:state
        or name.point.submit_num:state syntax.
        """
        if ":" in item:
            head, state_str = item.rsplit(":", 1)
        else:
            head, state_str = (item, None)
        if head.count("/") > 1:
            point_str, name_str, submit_num = head.split("/", 2)
        elif "/" in head:
            point_str, name_str = head.split("/", 1)
            submit_num = None
        elif head.count(".") > 1:
            name_str, point_str, submit_num = head.split(".", 2)
        elif "." in head:
            name_str, point_str = head.split(".", 1)
            submit_num = None
        else:
            name_str, point_str, submit_num = (head, None, None)
        return (point_str, name_str, submit_num, state_str)

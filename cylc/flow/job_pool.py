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
from copy import deepcopy

from cylc.flow import LOG
from cylc.flow.task_id import TaskID
from cylc.flow.task_state import (
    TASK_STATUS_READY, TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED)
from cylc.flow.data_messages_pb2 import PbJob, JDeltas
from cylc.flow.data_store_mgr import ID_DELIM

JOB_STATUSES_ALL = [
    TASK_STATUS_READY,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
]


class JobPool:
    """Pool of protobuf job messages."""
    # TODO: description, args, and types

    ERR_PREFIX_JOBID_MATCH = 'No matching jobs found: '
    ERR_PREFIX_JOB_NOT_ON_SEQUENCE = 'Invalid cycle point for job: '

    def __init__(self, suite, owner):
        self.suite = suite
        self.owner = owner
        self.workflow_id = f'{self.owner}{ID_DELIM}{self.suite}'
        self.pool = {}
        self.task_jobs = {}
        self.deltas = JDeltas()
        self.updates = {}
        self.updates_pending = False

    def insert_job(self, job_conf):
        """Insert job into pool."""
        update_time = time()
        job_owner = job_conf['owner']
        sub_num = job_conf['submit_num']
        name, point_string = TaskID.split(job_conf['task_id'])
        t_id = f'{self.workflow_id}{ID_DELIM}{point_string}{ID_DELIM}{name}'
        j_id = f'{t_id}{ID_DELIM}{sub_num}'
        j_buf = PbJob(
            stamp=f'{j_id}@{update_time}',
            id=j_id,
            submit_num=sub_num,
            state=JOB_STATUSES_ALL[0],
            task_proxy=t_id,
            batch_sys_name=job_conf['batch_system_name'],
            env_script=job_conf['env-script'],
            err_script=job_conf['err-script'],
            exit_script=job_conf['exit-script'],
            execution_time_limit=job_conf['execution_time_limit'],
            host=job_conf['platform']['name'],
            init_script=job_conf['init-script'],
            job_log_dir=job_conf['job_log_dir'],
            owner=job_owner,
            post_script=job_conf['post-script'],
            pre_script=job_conf['pre-script'],
            script=job_conf['script'],
            work_sub_dir=job_conf['work_d'],
            name=name,
            cycle_point=point_string,
        )
        j_buf.batch_sys_conf.extend(
            [f'{key}={val}'
             for key, val in job_conf['batch_system_conf'].items()])
        j_buf.directives.extend(
            [f'{key}={val}'
             for key, val in job_conf['directives'].items()])
        j_buf.environment.extend(
            [f'{key}={val}'
             for key, val in job_conf['environment'].items()])
        j_buf.param_env_tmpl.extend(
            [f'{key}={val}'
             for key, val in job_conf['param_env_tmpl'].items()])
        j_buf.param_var.extend(
            [f'{key}={val}'
             for key, val in job_conf['param_var'].items()])
        j_buf.extra_logs.extend(job_conf['logfiles'])
        self.updates[j_id] = j_buf
        self.task_jobs.setdefault(t_id, set()).add(j_id)
        self.updates_pending = True

    def add_job_msg(self, job_d, msg):
        """Add message to job."""
        update_time = time()
        point, name, sub_num = self.parse_job_item(job_d)
        j_id = (
            f'{self.workflow_id}{ID_DELIM}{point}'
            f'{ID_DELIM}{name}{ID_DELIM}{sub_num}')
        j_delta = PbJob(stamp=f'{j_id}@{update_time}')
        j_delta.messages.append(msg)
        self.updates.setdefault(j_id, PbJob(id=j_id)).MergeFrom(j_delta)
        self.updates_pending = True

    def reload_deltas(self):
        """Gather all current jobs as deltas after reload."""
        self.updates = deepcopy(self.pool)
        self.pool = {}
        if self.updates:
            self.updates_pending = True

    def remove_job(self, job_d):
        """Remove job from pool."""
        point, name, sub_num = self.parse_job_item(job_d)
        t_id = f'{self.workflow_id}{ID_DELIM}{point}{ID_DELIM}{name}'
        j_id = f'{t_id}{ID_DELIM}{sub_num}'
        # Jobs may be missing post restart/reload
        try:
            self.task_jobs[t_id].discard(j_id)
            self.deltas.pruned.append(j_id)
            self.updates_pending = True
        except KeyError:
            pass

    def remove_task_jobs(self, task_id):
        """Removed a task's jobs from the pool via task ID."""
        # Jobs/tasks may be missing post restart/reload
        try:
            for j_id in self.task_jobs[task_id]:
                self.deltas.pruned.append(j_id)
            del self.task_jobs[task_id]
            self.updates_pending = True
        except KeyError:
            pass

    def set_job_attr(self, job_d, attr_key, attr_val):
        """Set job attribute."""
        update_time = time()
        point, name, sub_num = self.parse_job_item(job_d)
        j_id = (
            f'{self.workflow_id}{ID_DELIM}{point}'
            f'{ID_DELIM}{name}{ID_DELIM}{sub_num}')
        j_delta = PbJob(stamp=f'{j_id}@{update_time}')
        setattr(j_delta, attr_key, attr_val)
        self.updates.setdefault(j_id, PbJob(id=j_id)).MergeFrom(j_delta)
        self.updates_pending = True

    def set_job_state(self, job_d, status):
        """Set job state."""
        update_time = time()
        point, name, sub_num = self.parse_job_item(job_d)
        j_id = (
            f'{self.workflow_id}{ID_DELIM}{point}'
            f'{ID_DELIM}{name}{ID_DELIM}{sub_num}')
        if status in JOB_STATUSES_ALL:
            j_delta = PbJob(
                stamp=f'{j_id}@{update_time}',
                state=status
            )
            self.updates.setdefault(
                j_id, PbJob(id=j_id)).MergeFrom(j_delta)
            self.updates_pending = True

    def set_job_time(self, job_d, event_key, time_str=None):
        """Set an event time in job pool object.

        Set values of both event_key + '_time' and event_key + '_time_string'.
        """
        update_time = time()
        point, name, sub_num = self.parse_job_item(job_d)
        j_id = (
            f'{self.workflow_id}{ID_DELIM}{point}'
            f'{ID_DELIM}{name}{ID_DELIM}{sub_num}')
        j_delta = PbJob(stamp=f'{j_id}@{update_time}')
        time_attr = f'{event_key}_time'
        setattr(j_delta, time_attr, time_str)
        self.updates.setdefault(j_id, PbJob(id=j_id)).MergeFrom(j_delta)
        self.updates_pending = True

    @staticmethod
    def parse_job_item(item):
        """Parse internal id
        point/name/submit_num
        or name.point.submit_num syntax (back compat).
        """
        submit_num = None
        if item.count('/') > 1:
            point_str, name_str, submit_num = item.split('/', 2)
        elif '/' in item:
            point_str, name_str = item.split('/', 1)
        elif item.count('.') > 1:
            name_str, point_str, submit_num = item.split('.', 2)
        elif '.' in item:
            name_str, point_str = item.split('.', 1)
        else:
            name_str, point_str = (item, None)
        try:
            sub_num = int(submit_num)
        except (TypeError, ValueError):
            sub_num = None
        return (point_str, name_str, sub_num)

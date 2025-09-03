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

from contextlib import suppress
import json
import logging
from typing import Any as Fixture
from unittest.mock import Mock

from cylc.flow import CYLC_LOG
from cylc.flow.job_runner_mgr import JOB_FILES_REMOVED_MESSAGE
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
)


async def test_run_job_cmd_no_hosts_error(
    flow,
    scheduler,
    start,
    mock_glbl_cfg,
    log_filter,
):
    """It should catch NoHostsError.

    NoHostsError's should be caught and handled rather than raised because
    they will cause problems (i.e. trigger shutdown) if they make it to the
    Scheduler.

    NoHostError's can occur in the poll & kill logic, this test ensures that
    these methods catch the NoHostsError and handle the event as a regular
    SSH failure by pushing the issue down the 255 callback.

    See https://github.com/cylc/cylc-flow/pull/5195
    """
    # define a platform
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
            [platforms]
                [[no-host-platform]]
        ''',
    )

    # define a workflow with a task which runs on that platform
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo'
            }
        },
        'runtime': {
            'foo': {
                'platform': 'no-host-platform'
            }
        }
    })

    # start the workflow
    schd: Scheduler = scheduler(id_)
    async with start(schd) as log:
        # set logging to debug level
        log.set_level(logging.DEBUG, CYLC_LOG)

        # tell Cylc the task is running on that platform
        schd.pool.get_tasks()[0].state_reset(TASK_STATUS_RUNNING)
        schd.pool.get_tasks()[0].platform = {
            'name': 'no-host-platform',
            'hosts': ['no-host-platform'],
        }

        # tell Cylc that that platform is not contactable
        # (i.e. all hosts are in bad_hosts)
        # (this casuses the NoHostsError to be raised)
        schd.task_job_mgr.bad_hosts.add('no-host-platform')

        # polling the task should not result in an error...
        schd.task_job_mgr.poll_task_jobs(schd.pool.get_tasks())

        # ...but the failure should be logged
        assert log_filter(
            contains='No available hosts for no-host-platform',
        )
        log.clear()

        # killing the task should not result in an error...
        schd.task_job_mgr.kill_task_jobs(schd.pool.get_tasks())

        # ...but the failure should be logged
        assert log_filter(
            contains='No available hosts for no-host-platform',
        )


async def test__run_job_cmd_logs_platform_lookup_fail(
    one_conf: Fixture, flow: Fixture, scheduler: Fixture, run: Fixture,
    db_select: Fixture, caplog: Fixture
) -> None:
    """TaskJobMg._run_job_cmd handles failure to get platform."""
    id_: str = flow(one_conf)
    schd: 'Scheduler' = scheduler(id_, paused_start=True)
    # Run
    async with run(schd):
        from types import SimpleNamespace
        schd.task_job_mgr._run_job_cmd(
            schd.task_job_mgr.JOBS_POLL,
            [SimpleNamespace(platform={'name': 'culdee fell summit'})],
            None,
            None
        )
        warning = caplog.records[-1]
        assert warning.levelname == 'ERROR'
        assert 'Unable to run command jobs-poll' in warning.msg


async def test__prep_submit_task_job_impl_handles_execution_time_limit(
    flow: Fixture,
    scheduler: Fixture,
    start: Fixture,
):
    """Ensure that emptying the execution time limit unsets it.

    Previously unsetting the etl by either broadcast or reload
    would not unset a previous etl.

    See https://github.com/cylc/cylc-flow/issues/5891
    """
    id_ = flow({
        "scheduling": {
            "cycling mode": "integer",
            "graph": {"R1": "a"}
        },
        "runtime": {
            "root": {},
            "a": {
                "script": "sleep 10",
                "execution time limit": 'PT5S'
            }
        }
    })

    # Run in live mode - function not called in sim mode.
    schd = scheduler(id_, run_mode='live')
    async with start(schd):
        task_a = schd.pool.get_tasks()[0]
        # We're not interested in the job file stuff, just
        # in the summary state.
        with suppress(FileExistsError):
            schd.task_job_mgr._prep_submit_task_job_impl(
                task_a, task_a.tdef.rtconfig
            )
        assert task_a.summary['execution_time_limit'] == 5.0

        # If we delete the etl it gets deleted in the summary:
        task_a.tdef.rtconfig['execution time limit'] = None
        with suppress(FileExistsError):
            schd.task_job_mgr._prep_submit_task_job_impl(
                task_a, task_a.tdef.rtconfig
            )
        assert not task_a.summary.get('execution_time_limit', '')

        # put everything back and test broadcast too.
        task_a.tdef.rtconfig['execution time limit'] = 5.0
        task_a.summary['execution_time_limit'] = 5.0
        schd.broadcast_mgr.broadcasts = {
            '1': {'a': {'execution time limit': None}}}
        with suppress(FileExistsError):
            # We run a higher level function here to ensure
            # that the broadcast is applied.
            schd.task_job_mgr._prep_submit_task_job(task_a)
        assert not task_a.summary.get('execution_time_limit', '')


async def test_broadcast_platform_change(
    mock_glbl_cfg,
    flow,
    scheduler,
    start,
    log_filter,
):
    """Broadcast can change task platform.

    Even after host selection failure.

    see https://github.com/cylc/cylc-flow/issues/6320
    """
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
            [platforms]
                [[foo]]
                    hosts = food
        ''')

    id_ = flow({
        "scheduling": {"graph": {"R1": "mytask"}},
        # Platform = None doesn't cause this issue!
        "runtime": {"mytask": {"platform": "localhost"}}})

    schd: Scheduler = scheduler(id_, run_mode='live')

    async with start(schd):
        # Change the task platform with broadcast:
        schd.broadcast_mgr.put_broadcast(
            ['1'], ['mytask'], [{'platform': 'foo'}])

        # Simulate prior failure to contact hosts:
        schd.bad_hosts.add('food')

        # Attempt job submission:
        schd.submit_task_jobs(schd.pool.get_tasks())

        # Check that task platform hasn't become "localhost":
        assert schd.pool.get_tasks()[0].platform['name'] == 'foo'
        # ... and that remote init failed because all hosts bad:
        assert log_filter(regex=r"platform: foo .*\(no hosts were reachable\)")


async def test_poll_job_deleted_log_folder(
    one_conf, flow, scheduler, start, log_filter
):
    """Capture a task error caused by polling finding the job log dir deleted.

    https://github.com/cylc/cylc-flow/issues/6425
    """
    response = {
        'run_signal': JOB_FILES_REMOVED_MESSAGE,
        'run_status': 1,
        'job_runner_exit_polled': 1,
    }
    schd: Scheduler = scheduler(flow(one_conf))
    async with start(schd):
        itask = schd.pool.get_tasks()[0]
        itask.submit_num = 1
        job_id = itask.job_tokens.relative_id
        schd.task_job_mgr._poll_task_job_callback(
            itask,
            cmd_ctx=Mock(),
            line=f'2025-02-13T12:08:30Z|{job_id}|{json.dumps(response)}',
        )
        assert itask.state(TASK_STATUS_FAILED)

    assert log_filter(
        logging.ERROR, f"job log directory {job_id} no longer exists"
    )

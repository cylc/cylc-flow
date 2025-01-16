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


import asyncio
import logging

from async_timeout import timeout as async_timeout
import pytest

from cylc.flow.commands import (
    kill_tasks,
    run_cmd,
)
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUBMIT_FAILED,
)


async def task_state(itask: TaskProxy, state: str, timeout=4, **kwargs):
    """Await task state."""
    async with async_timeout(timeout):
        while not itask.state(state, **kwargs):
            await asyncio.sleep(0.1)


async def test_simulation(flow, scheduler, run):
    """Test killing a running task in simulation mode."""
    conf = {
        'scheduling': {
            'graph': {
                'R1': 'foo',
            },
        },
        'runtime': {
            'root': {
                'simulation': {
                    'default run length': 'PT30S',
                },
            },
        },
    }
    schd: Scheduler = scheduler(flow(conf), paused_start=False)
    async with run(schd):
        itask = schd.pool.get_tasks()[0]
        await task_state(itask, TASK_STATUS_RUNNING)

        await run_cmd(kill_tasks(schd, [itask.identity]))
        await task_state(itask, TASK_STATUS_FAILED, is_held=True)
        assert schd.check_workflow_stalled()


async def test_kill_preparing(
    one_conf,
    flow,
    scheduler,
    start,
    monkeypatch: pytest.MonkeyPatch,
    log_filter,
):
    """Test killing a preparing task."""
    schd: Scheduler = scheduler(
        flow(one_conf), run_mode='live', paused_start=False
    )
    async with start(schd):
        # Make the task indefinitely preparing:
        monkeypatch.setattr(
            schd.task_job_mgr, '_prep_submit_task_job', lambda *a, **k: None
        )
        itask = schd.pool.get_tasks()[0]
        assert itask.state(TASK_STATUS_WAITING, is_held=False)
        schd.start_job_submission([itask])

        await run_cmd(kill_tasks(schd, [itask.tokens.relative_id]))
        assert itask.state(TASK_STATUS_SUBMIT_FAILED, is_held=True)
        assert log_filter(logging.ERROR, 'killed in job prep')

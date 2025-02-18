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
from secrets import token_hex
import sys
from unittest.mock import Mock

import pytest

from cylc.flow.commands import (
    kill_tasks,
    run_cmd,
)
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_remote_mgr import (
    REMOTE_FILE_INSTALL_DONE,
    REMOTE_FILE_INSTALL_IN_PROGRESS,
    REMOTE_INIT_DONE,
    REMOTE_INIT_IN_PROGRESS,
)
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUBMIT_FAILED,
)


if sys.version_info[:2] >= (3, 11):
    from asyncio import timeout as async_timeout
else:
    from async_timeout import timeout as async_timeout


LOCALHOST = 'localhost'


async def task_state(itask: TaskProxy, state: str, timeout=4, **kwargs):
    """Await task state."""
    async with async_timeout(timeout):
        while not itask.state(state, **kwargs):
            await asyncio.sleep(0.1)


def patch_remote_init(schd: Scheduler, value: str):
    """Set remote init state."""
    schd.task_job_mgr.task_remote_mgr.remote_init_map[LOCALHOST] = value


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
    flow, scheduler, run, monkeypatch: pytest.MonkeyPatch, log_filter
):
    """Test killing a preparing task."""
    schd: Scheduler = scheduler(
        flow('foo'), run_mode='live', paused_start=False
    )
    async with run(schd):
        # Make the task indefinitely preparing:
        monkeypatch.setattr(
            schd.task_job_mgr, '_prep_submit_task_job', Mock(return_value=None)
        )
        itask = schd.pool.get_tasks()[0]
        await task_state(itask, TASK_STATUS_PREPARING, is_held=False)

        await run_cmd(kill_tasks(schd, [itask.identity]))
        await task_state(itask, TASK_STATUS_SUBMIT_FAILED, is_held=True)
        assert log_filter(logging.ERROR, 'killed in job prep')


async def test_kill_preparing_pipeline(
    flow, scheduler, start, monkeypatch: pytest.MonkeyPatch
):
    """Test killing a preparing task through various stages of the preparing
    pipeline that involve submitting subprocesses and waiting for them to
    complete."""
    # Make localhost look like a remote target so we can test
    # remote init/file install stages:
    monkeypatch.setattr(
        'cylc.flow.task_job_mgr.get_localhost_install_target',
        Mock(return_value=token_hex()),
    )

    schd: Scheduler = scheduler(
        flow('one'), run_mode='live', paused_start=False
    )
    async with start(schd):
        remote_mgr = schd.task_job_mgr.task_remote_mgr
        mock_eval_platform = Mock(return_value=None)
        monkeypatch.setattr(remote_mgr, 'eval_platform', mock_eval_platform)
        mock_remote_init = Mock()
        monkeypatch.setattr(remote_mgr, 'remote_init', mock_remote_init)
        mock_file_install = Mock()
        monkeypatch.setattr(remote_mgr, 'file_install', mock_file_install)
        itask = schd.pool.get_tasks()[0]

        # Platform eval:
        schd.submit_task_jobs([itask])
        assert itask.state(TASK_STATUS_PREPARING)
        assert schd.release_tasks_to_run() is False
        await run_cmd(kill_tasks(schd, [itask.identity]))
        assert itask.state(TASK_STATUS_SUBMIT_FAILED)
        assert schd.release_tasks_to_run() is False
        # Set to finished:
        mock_eval_platform.return_value = LOCALHOST
        # Should not submit after finish because it was killed:
        assert schd.release_tasks_to_run() is False

        # Remote init:
        patch_remote_init(schd, REMOTE_INIT_IN_PROGRESS)
        schd.submit_task_jobs([itask])
        assert itask.state(TASK_STATUS_PREPARING)
        assert schd.release_tasks_to_run() is False
        await run_cmd(kill_tasks(schd, [itask.identity]))
        assert itask.state(TASK_STATUS_SUBMIT_FAILED)
        assert schd.release_tasks_to_run() is False
        # Set to finished:
        patch_remote_init(schd, REMOTE_INIT_DONE)
        # Should not submit after finish because it was killed:
        assert schd.release_tasks_to_run() is False
        assert not mock_remote_init.called

        # Remote file install:
        patch_remote_init(schd, REMOTE_FILE_INSTALL_IN_PROGRESS)
        schd.submit_task_jobs([itask])
        assert itask.state(TASK_STATUS_PREPARING)
        assert schd.release_tasks_to_run() is False
        await run_cmd(kill_tasks(schd, [itask.identity]))
        assert itask.state(TASK_STATUS_SUBMIT_FAILED)
        assert schd.release_tasks_to_run() is False
        # Set to finished:
        patch_remote_init(schd, REMOTE_FILE_INSTALL_DONE)
        # Should not submit after finish because it was killed:
        assert schd.release_tasks_to_run() is False
        assert not mock_file_install.called

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
import pytest
from typing import Any, Callable

from cylc.flow.exceptions import CylcError
from cylc.flow.scheduler import Scheduler

Fixture = Any


async def test_is_paused_after_stop(
        one_conf: Fixture, flow: Fixture, scheduler: Fixture, run: Fixture,
        db_select: Fixture):
    """Test the paused status is unset on normal shutdown."""
    reg: str = flow(one_conf)
    schd: 'Scheduler' = scheduler(reg, paused_start=True)
    # Run
    async with run(schd):
        assert not schd.is_restart
        assert schd.is_paused
    # Stopped
    assert ('is_paused', '1') not in db_select(schd, False, 'workflow_params')
    # Restart
    schd = scheduler(reg, paused_start=None)
    async with run(schd):
        assert schd.is_restart
        assert not schd.is_paused


async def test_is_paused_after_crash(
        one_conf: Fixture, flow: Fixture, scheduler: Fixture, run: Fixture,
        db_select: Fixture):
    """Test the paused status is not unset for an interrupted workflow."""
    reg: str = flow(one_conf)
    schd: 'Scheduler' = scheduler(reg, paused_start=True)

    def ctrl_c():
        raise asyncio.CancelledError("Mock keyboard interrupt")
    # Patch this part of the main loop
    _schd_workflow_shutdown = schd.workflow_shutdown
    setattr(schd, 'workflow_shutdown', ctrl_c)

    # Run
    with pytest.raises(asyncio.CancelledError):
        async with run(schd):
            assert not schd.is_restart
            assert schd.is_paused
    # Stopped
    assert ('is_paused', '1') in db_select(schd, False, 'workflow_params')
    # Reset patched method
    setattr(schd, 'workflow_shutdown', _schd_workflow_shutdown)
    # Restart
    schd = scheduler(reg, paused_start=None)
    async with run(schd):
        assert schd.is_restart
        assert schd.is_paused


async def test_shutdown_CylcError_log(one: Scheduler, run: Callable):
    """Test that if a CylcError occurs during shutdown, it is
    logged in one line."""
    schd = one

    async def mock_shutdown(*a, **k):
        raise CylcError("Error on shutdown")
    setattr(schd, '_shutdown', mock_shutdown)

    log: pytest.LogCaptureFixture
    with pytest.raises(CylcError) as exc:
        async with run(schd) as log:
            pass
    assert str(exc.value) == "Error on shutdown"
    last_record = log.records[-1]
    assert last_record.message == "CylcError: Error on shutdown"
    assert last_record.levelno == logging.ERROR


async def test_shutdown_general_exception_log(one: Scheduler, run: Callable):
    """Test that if a non-CylcError occurs during shutdown, it is
    logged with traceback (but not excessive)."""
    schd = one

    async def mock_shutdown(*a, **k):
        raise ValueError("Error on shutdown")
    setattr(schd, '_shutdown', mock_shutdown)

    log: pytest.LogCaptureFixture
    with pytest.raises(ValueError) as exc:
        async with run(schd) as log:
            pass
    assert str(exc.value) == "Error on shutdown"
    last_record = log.records[-1]
    assert last_record.message == "Error on shutdown"
    assert last_record.levelno == logging.ERROR
    assert last_record.exc_text is not None
    assert last_record.exc_text.startswith("Traceback (most recent call last)")
    assert ("During handling of the above exception, "
            "another exception occurred") not in last_record.exc_text


async def test_holding_tasks_whilst_scheduler_paused(
    capture_submission,
    flow,
    one_conf,
    run,
    scheduler,
):
    """It should hold tasks irrespective of workflow state.

    See https://github.com/cylc/cylc-flow/issues/4278
    """
    reg = flow(one_conf)
    one = scheduler(reg, paused_start=True)

    # run the workflow
    async with run(one):
        # capture any job submissions
        submitted_tasks = capture_submission(one)
        assert one.pre_prep_tasks == []
        assert submitted_tasks == set()

        # release runahead/queued tasks
        # (nothing should happen because the scheduler is paused)
        one.pool.release_runahead_tasks()
        one.release_queued_tasks()
        assert one.pre_prep_tasks == []
        assert submitted_tasks == set()

        # hold all tasks & resume the workflow
        one.command_hold(['*/*'])
        one.resume_workflow()

        # release queued tasks
        # (there should be no change because the task is still held)
        one.release_queued_tasks()
        assert one.pre_prep_tasks == []
        assert submitted_tasks == set()

        # release all tasks
        one.command_release(['*/*'])

        # release queued tasks
        # (the task should be submitted)
        one.release_queued_tasks()
        assert len(one.pre_prep_tasks) == 1
        assert len(submitted_tasks) == 1

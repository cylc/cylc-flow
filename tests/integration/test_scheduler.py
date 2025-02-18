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
from pathlib import Path
import pytest
import re
from signal import SIGHUP, SIGINT, SIGTERM
from typing import Any, Callable

from cylc.flow import commands
from cylc.flow.exceptions import CylcError
from cylc.flow.flow_mgr import FLOW_ALL
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.scheduler import Scheduler, SchedulerStop
from cylc.flow.task_state import (
    TASK_STATUS_WAITING,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED
)

from cylc.flow.workflow_status import AutoRestartMode, StopMode


Fixture = Any


TRACEBACK_MSG = "Traceback (most recent call last):"


async def test_is_paused_after_stop(
        one_conf: Fixture, flow: Fixture, scheduler: Fixture, run: Fixture,
        db_select: Fixture):
    """Test the paused status is unset on normal shutdown."""
    id_: str = flow(one_conf)
    schd: 'Scheduler' = scheduler(id_, paused_start=True)
    # Run
    async with run(schd):
        assert not schd.is_restart
        assert schd.is_paused
    # Stopped
    assert ('is_paused', '1') not in db_select(schd, False, 'workflow_params')
    # Restart
    schd = scheduler(id_, paused_start=None)
    async with run(schd):
        assert schd.is_restart
        assert not schd.is_paused


async def test_is_paused_after_crash(
        one_conf: Fixture, flow: Fixture, scheduler: Fixture, run: Fixture,
        db_select: Fixture):
    """Test the paused status is not unset for an interrupted workflow."""
    id_: str = flow(one_conf)
    schd: 'Scheduler' = scheduler(id_, paused_start=True)

    def ctrl_c():
        raise asyncio.CancelledError("Mock keyboard interrupt")
    # Patch this part of the main loop
    _schd_workflow_shutdown = schd.workflow_shutdown
    schd.workflow_shutdown = ctrl_c

    # Run
    with pytest.raises(asyncio.CancelledError):
        async with run(schd):
            assert not schd.is_restart
            assert schd.is_paused
    # Stopped
    assert ('is_paused', '1') in db_select(schd, False, 'workflow_params')
    # Reset patched method
    schd.workflow_shutdown = _schd_workflow_shutdown
    # Restart
    schd = scheduler(id_, paused_start=None)
    async with run(schd):
        assert schd.is_restart
        assert schd.is_paused


async def test_shutdown_CylcError_log(one: Scheduler, run: Callable):
    """Test that if a CylcError occurs during shutdown, it is
    logged in one line."""
    schd = one

    # patch the shutdown to raise an error
    async def mock_shutdown(*a, **k):
        raise CylcError("Error on shutdown")
    schd._shutdown = mock_shutdown

    # run the workflow
    log: pytest.LogCaptureFixture
    with pytest.raises(CylcError) as exc:
        async with run(schd) as log:
            pass

    # check the log records after attempted shutdown
    assert str(exc.value) == "Error on shutdown"
    last_record = log.records[-1]
    assert last_record.message == "CylcError: Error on shutdown"
    assert last_record.levelno == logging.ERROR

    # shut down the scheduler properly
    await Scheduler._shutdown(schd, SchedulerStop('because I said so'))


async def test_shutdown_general_exception_log(one: Scheduler, run: Callable):
    """Test that if a non-CylcError occurs during shutdown, it is
    logged with traceback (but not excessive)."""
    schd = one

    # patch the shutdown to raise an error
    async def mock_shutdown(*a, **k):
        raise ValueError("Error on shutdown")
    schd._shutdown = mock_shutdown

    # run the workflow
    log: pytest.LogCaptureFixture
    with pytest.raises(ValueError) as exc:
        async with run(schd) as log:
            pass

    # check the log records after attempted shutdown
    assert str(exc.value) == "Error on shutdown"
    last_record = log.records[-1]
    assert last_record.message == "Error on shutdown"
    assert last_record.levelno == logging.ERROR
    assert last_record.exc_text is not None
    assert last_record.exc_text.startswith(TRACEBACK_MSG)
    assert ("During handling of the above exception, "
            "another exception occurred") not in last_record.exc_text

    # shut down the scheduler properly
    await Scheduler._shutdown(schd, SchedulerStop('because I said so'))


async def test_holding_tasks_whilst_scheduler_paused(
    capture_submission,
    flow,
    one_conf,
    start,
    scheduler,
):
    """It should hold tasks irrespective of workflow state.

    See https://github.com/cylc/cylc-flow/issues/4278
    """
    id_ = flow(one_conf)
    one = scheduler(id_, paused_start=True)

    # run the workflow
    async with start(one):
        # capture any job submissions
        submitted_tasks = capture_submission(one)
        assert submitted_tasks == set()

        # release runahead/queued tasks
        # (nothing should happen because the scheduler is paused)
        one.pool.release_runahead_tasks()
        one.release_tasks_to_run()
        assert submitted_tasks == set()

        # hold all tasks & resume the workflow
        await commands.run_cmd(commands.hold(one, ['*/*']))
        one.resume_workflow()

        # release queued tasks
        # (there should be no change because the task is still held)
        one.release_tasks_to_run()
        assert submitted_tasks == set()

        # release all tasks
        await commands.run_cmd(commands.release(one, ['*/*']))

        # release queued tasks
        # (the task should be submitted)
        one.release_tasks_to_run()
        assert len(submitted_tasks) == 1


async def test_no_poll_waiting_tasks(
    capture_polling,
    flow,
    one_conf,
    start,
    scheduler,
):
    """Waiting tasks shouldn't be polled.

    If a waiting task previously it will have the submit number of its previous
    job, and polling would erroneously return the state of that job.

    See https://github.com/cylc/cylc-flow/issues/4658
    """
    id_: str = flow(one_conf)
    # start the scheduler in live mode in order to activate regular polling
    # logic
    one: Scheduler = scheduler(id_, run_mode='live')

    log: pytest.LogCaptureFixture
    async with start(one) as log:
        # Test assumes start up with a waiting task.
        task = (one.pool.get_tasks())[0]
        assert task.state.status == TASK_STATUS_WAITING

        polled_tasks = capture_polling(one)

        # Waiting tasks should not be polled.
        await commands.run_cmd(commands.poll_tasks(one, ['*/*']))
        assert polled_tasks == set()

        # Even if they have a submit number.
        task.submit_num = 1
        await commands.run_cmd(commands.poll_tasks(one, ['*/*']))
        assert len(polled_tasks) == 0

        # But these states should be:
        for state in [
            TASK_STATUS_SUBMIT_FAILED,
            TASK_STATUS_FAILED,
            TASK_STATUS_SUBMITTED,
            TASK_STATUS_RUNNING
        ]:
            task.state.status = state
            await commands.run_cmd(commands.poll_tasks(one, ['*/*']))
            assert len(polled_tasks) == 1
            polled_tasks.clear()

        # Shut down with a running task.
        task.state.status = TASK_STATUS_RUNNING

    # For good measure, check the faked running task is reported at shutdown.
    assert "Orphaned tasks:\n* 1/one (running)" in log.messages


async def test_unexpected_ParsecError(
    one: Scheduler,
    start: Callable,
    log_filter: Callable,
    monkeypatch: pytest.MonkeyPatch
):
    """Test that ParsecErrors - that occur at any time other than config load
    when running a workflow - are displayed with traceback, because they are
    not expected."""
    log: pytest.LogCaptureFixture

    def raise_ParsecError(*a, **k):
        raise ParsecError("Mock error")

    monkeypatch.setattr(one, '_configure_contact', raise_ParsecError)

    with pytest.raises(ParsecError):
        async with start(one) as log:
            pass

    assert log_filter(
        logging.CRITICAL,
        exact_match="Workflow shutting down - Mock error"
    )
    assert TRACEBACK_MSG in log.text


async def test_error_during_auto_restart(
    one: Scheduler,
    run: Callable,
    log_filter: Callable,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that an error during auto-restart does not get swallowed"""
    log: pytest.LogCaptureFixture
    err_msg = "Mock error: sugar in water"

    def mock_auto_restart(*a, **k):
        raise RuntimeError(err_msg)

    monkeypatch.setattr(one, 'workflow_auto_restart', mock_auto_restart)
    monkeypatch.setattr(
        one, 'auto_restart_mode', AutoRestartMode.RESTART_NORMAL
    )

    with pytest.raises(RuntimeError, match=err_msg):
        async with run(one) as log:
            pass

    assert log_filter(logging.ERROR, err_msg)
    assert TRACEBACK_MSG in log.text


async def test_uuid_unchanged_on_restart(
    one: Scheduler,
    scheduler: Callable,
    start: Callable,
):
    """Restart gets UUID from Database:

    See https://github.com/cylc/cylc-flow/issues/5615

    Process:
       * Create a scheduler then shut it down.
       * Create a new scheduler for the same workflow and check that it has
         retrieved the UUID from the Daatabase.
    """
    uuid_re = re.compile('CYLC_WORKFLOW_UUID=(.*)')
    contact_file = Path(one.workflow_run_dir) / '.service/contact'

    async with start(one):
        pass

    schd = scheduler(one.workflow_name, paused_start=True)
    async with start(schd):
        # UUID in contact file should be the same as that set in the database
        # and the scheduler.
        cf_uuid = uuid_re.findall(contact_file.read_text())
        assert cf_uuid == [schd.uuid_str]


async def test_restart_timeout(
    flow,
    one_conf,
    scheduler,
    run,
    log_filter,
    complete,
    capture_submission,
):
    """It should wait for user input if there are no tasks in the pool.

    When restarting a completed workflow there are no tasks in the pool so
    the scheduler is inclined to shutdown before the user has had the chance
    to trigger tasks in order to allow the workflow to continue.

    In order to make this easier, the scheduler should enter the paused state
    and wait around for a configured period before shutting itself down.

    See: https://github.com/cylc/cylc-flow/issues/5078
    """
    id_ = flow(one_conf)

    # run the workflow to completion
    schd: Scheduler = scheduler(id_, paused_start=False)
    async with run(schd):
        await complete(schd)

    # restart the completed workflow
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # it should detect that the workflow has completed and alert the user
        assert log_filter(
            logging.WARNING,
            contains='This workflow already ran to completion.'
        )

        # it should activate a timeout
        assert log_filter(logging.WARNING, contains='restart timer starts NOW')

        capture_submission(schd)
        # when we trigger tasks the timeout should be cleared
        schd.pool.force_trigger_tasks(['1/one'], [FLOW_ALL])

        await asyncio.sleep(0)  # yield control to the main loop
        assert log_filter(logging.INFO, contains='restart timer stopped')


@pytest.mark.parametrize("signal", ((SIGHUP), (SIGINT), (SIGTERM)))
async def test_signal_escalation(one, start, signal, log_filter):
    """Double signal should escalate shutdown.

    If a term-like signal is received whilst the workflow is already stopping
    in NOW mode, then the shutdown should be escalated to NOW_NOW
    mode.

    See https://github.com/cylc/cylc-flow/pull/6444
    """
    async with start(one):
        # put the workflow in the stopping state
        one._set_stop(StopMode.REQUEST_CLEAN)
        assert one.stop_mode.name == 'REQUEST_CLEAN'

        # one signal should escalate this from CLEAN to NOW
        one._handle_signal(signal, None)
        assert log_filter(contains=signal.name)
        assert one.stop_mode.name == 'REQUEST_NOW'

        # two signals should escalate this from NOW to NOW_NOW
        one._handle_signal(signal, None)
        assert one.stop_mode.name == 'REQUEST_NOW_NOW'

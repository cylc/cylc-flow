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
import sys

import pytest
from types import MethodType

from cylc.flow.scheduler import SchedulerError


if sys.version_info[:2] >= (3, 11):
    from asyncio import timeout as async_timeout
else:
    from async_timeout import timeout as async_timeout


EVENTS = (
    'startup',
    'shutdown',
    'abort',
    'workflow timeout',
    'stall',
    'stall timeout',
    'inactivity timeout',
    'restart timeout',
)


@pytest.fixture
async def test_scheduler(flow, scheduler, capcall):
    events = capcall(
        'cylc.flow.scheduler.Scheduler.run_event_handlers',
    )

    def get_events():
        return {e[0][1] for e in events}

    def _schd(config=None, **opts):
        id_ = flow({
            'scheduler': {
                'events': {
                    'mail events': ', '.join(EVENTS),
                    **(config or {}),
                },
            },
            'scheduling': {
                'graph': {
                    'R1': 'a'
                }
            },
            'runtime': {
                'a': {
                    'simulation': {
                        'default run length': 'PT0S',
                    }
                }
            },
        })
        schd = scheduler(id_, **opts)
        schd.get_events = get_events
        return schd

    return _schd


async def test_startup_and_shutdown(test_scheduler, run):
    """Test the startup and shutdown events.

    * "startup" should fire every time a scheduler is started.
    * "shutdown" should fire every time a scheduler does a controlled exit.
      (i.e. excluding aborts on unexpected internal errors).
    """
    schd = test_scheduler()
    async with run(schd):
        # NOTE: the "startup" event is only yielded with "run" not "start"
        pass
    assert schd.get_events() == {'startup', 'shutdown'}


async def test_workflow_timeout(test_scheduler, run):
    """Test the workflow timeout.

    This counts down from scheduler start.
    """
    schd = test_scheduler({'workflow timeout': 'PT0S'})
    async with async_timeout(4):
        async with run(schd):
            await asyncio.sleep(0.1)
    assert schd.get_events() == {'startup', 'workflow timeout', 'shutdown'}


async def test_inactivity_timeout(test_scheduler, start):
    """Test the inactivity timeout.

    This counts down from things like state changes.
    """
    schd = test_scheduler({
        'inactivity timeout': 'PT0S',
        'abort on inactivity timeout': 'True',
    })
    async with async_timeout(4):
        with pytest.raises(SchedulerError):
            async with start(schd):
                await asyncio.sleep(0)
                await schd._main_loop()
    assert schd.get_events() == {'inactivity timeout', 'shutdown'}


async def test_abort(test_scheduler, run):
    """Test abort.

    This should fire when uncaught internal exceptions are raised.

    Note, this is orthogonal to shutdown (i.e. a scheduler either shuts down or
    aborts, not both).

    Note, this is orthogonal to the "abort on <event>" configurations.
    """
    schd = test_scheduler()

    # get the main-loop to raise an exception
    def killer():
        raise Exception(':(')

    schd._main_loop = killer

    # start the scheduler and wait for it to hit the exception
    with pytest.raises(Exception):
        async with run(schd):
            for _ in range(10):
                # allow initialisation to complete
                await asyncio.sleep(0.1)

    # the abort event should be called
    # note, "abort" and "shutdown" are orthogonal
    assert schd.get_events() == {'startup', 'abort'}


async def test_stall(test_scheduler, start):
    """Test the stall event.

    This should fire when the scheduler enters the stalled state.
    """
    schd = test_scheduler()
    async with start(schd):
        # set the failed output
        schd.pool.spawn_on_output(
            schd.pool.get_tasks()[0],
            'failed'
        )

        # set the failed status
        schd.pool.get_tasks()[0].state_reset('failed')

        # check for workflow stall condition
        schd.is_paused = False
        schd.check_workflow_stalled()

    assert schd.get_events() == {'shutdown', 'stall'}


async def test_restart_timeout(test_scheduler, scheduler, run, complete):
    """Test restart timeout.

    This should fire when a completed workflow is restarted.
    """
    schd = test_scheduler({'restart timeout': 'PT0S'}, paused_start=False)

    # run to completion
    async with run(schd):
        await complete(schd)
    assert schd.get_events() == {'startup', 'shutdown'}

    # restart
    schd2 = scheduler(schd.workflow)
    schd2.get_events = schd.get_events
    async with run(schd2):
        await asyncio.sleep(0.1)
    assert schd2.get_events() == {'startup', 'restart timeout', 'shutdown'}


async def test_shutdown_handler_timeout_kill(
    test_scheduler, run, monkeypatch, mock_glbl_cfg, caplog
):
    """Test shutdown handlers get killed on the process pool timeout.

    Has to be done differently as the process pool is closed during shutdown.
    See GitHub #6639

    """
    def mock_run_event_handlers(self, event, reason=""):
        """To replace scheduler.run_event_handlers(...).

        Run workflow event handlers even in simulation mode.

        """
        self.workflow_event_handler.handle(self, event, str(reason))

    # Configure a long-running shutdown handler.
    schd = test_scheduler({'shutdown handlers': 'sleep 10; echo'})

    # Set a low process pool timeout value.
    mock_glbl_cfg(
        'cylc.flow.subprocpool.glbl_cfg',
        '''
        [scheduler]
            process pool timeout = PT1S
        '''
    )

    async with async_timeout(30):
        async with run(schd):
            # Replace a scheduler method, to call handlers in simulation mode.
            monkeypatch.setattr(
                schd,
                'run_event_handlers',
                MethodType(mock_run_event_handlers, schd),
            )
            await asyncio.sleep(0.1)

    assert (
        "[('workflow-event-handler-00', 'shutdown') err] killed on timeout (PT1S)"
        in caplog.text
    )

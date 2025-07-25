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
from types import MethodType

from async_timeout import timeout as async_timeout
import pytest

from cylc.flow.scheduler import SchedulerError
from cylc.flow.workflow_events import WorkflowEventHandler


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
    schd = test_scheduler({
        'shutdown handlers': 'sleep 10; echo',
        'mail events': '',
    })

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
        "[('workflow-event-handler-00', 'shutdown') err] killed on "
        "timeout (PT1S)"
    ) in caplog.text


TEMPLATES = [
    # perfectly valid
    pytest.param('%(workflow)s', id='good'),
    # no template variable of that name
    pytest.param('%(no_such_variable)s', id='bad'),
    # missing the 's'
    pytest.param('%(broken_syntax)', id='ugly'),
]


@pytest.mark.parametrize('template', TEMPLATES)
async def test_mail_footer_template(
    mod_one,  # use the same scheduler for each test
    start,
    mock_glbl_cfg,
    log_filter,
    capcall,
    template,
):
    """It should handle templating issues with the mail footer."""
    # prevent emails from being sent
    mail_calls = capcall(
        'cylc.flow.workflow_events.WorkflowEventHandler._send_mail'
    )

    # configure Cylc to send an email on startup with the configured footer
    mock_glbl_cfg(
        'cylc.flow.workflow_events.glbl_cfg',
        f'''
            [scheduler]
                [[mail]]
                    footer = 'footer={template}'
                [[events]]
                    mail events = startup
        ''',
    )

    # start the workflow and get it to send an email
    async with start(mod_one) as one_log:
        one_log.clear()  # clear previous log messages
        mod_one.workflow_event_handler.handle(
            mod_one,
            WorkflowEventHandler.EVENT_STARTUP,
            'event message'
        )

    # warnings should appear only when the template is invalid
    should_log = 'workflow' not in template

    # check that template issues are handled correctly
    assert bool(log_filter(
        contains='Ignoring bad mail footer template',
    )) == should_log
    assert bool(log_filter(
        contains=template,
    )) == should_log

    # check that the mail is sent even if there are issues with the footer
    assert len(mail_calls) == 1


@pytest.mark.parametrize('template', TEMPLATES)
async def test_custom_event_handler_template(
    mod_one,  # use the same scheduler for each test
    start,
    mock_glbl_cfg,
    log_filter,
    template,
):
    """It should handle templating issues with custom event handlers."""
    # configure Cylc to send an email on startup with the configured footer
    mock_glbl_cfg(
        'cylc.flow.workflow_events.glbl_cfg',
        f'''
            [scheduler]
                [[events]]
                    startup handlers = echo "{template}"
        '''
    )

    # start the workflow and get it to send an email
    async with start(mod_one) as one_log:
        one_log.clear()  # clear previous log messages
        mod_one.workflow_event_handler.handle(
            mod_one,
            WorkflowEventHandler.EVENT_STARTUP,
            'event message'
        )

    # warnings should appear only when the template is invalid
    should_log = 'workflow' not in template

    # check that template issues are handled correctly
    assert bool(log_filter(
        contains='bad template',
    )) == should_log
    assert bool(log_filter(
        contains=template,
    )) == should_log

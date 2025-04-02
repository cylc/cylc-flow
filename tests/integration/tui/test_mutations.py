#!/usr/bin/env python3
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

import pytest

from cylc.flow.exceptions import ClientError


async def process_command(schd, tries=10, interval=0.1):
    """Wait for command(s) to be queued and run.

    Waits for at least one command to be queued and for all queued commands to
    be run.
    """
    # wait for the command to be queued
    for _try in range(tries):
        await asyncio.sleep(interval)
        if not schd.command_queue.empty():
            break
    else:
        raise Exception(f'No command was queued after {tries * interval}s')

    # run the command
    await schd.process_command_queue()

    # push out updates
    await schd.update_data_structure()

    # make sure it ran
    assert schd.command_queue.empty(), 'command queue has not emptied'


async def test_online_mutation(
    one_conf,
    flow,
    scheduler,
    start,
    rakiura,
    monkeypatch,
    log_filter,
):
    """Test a simple workflow with one task."""
    id_ = flow(one_conf, name='one')
    schd = scheduler(id_)
    with rakiura(size='80,15') as rk:
        async with start(schd):
            await schd.update_data_structure()
            assert schd.command_queue.empty()

            # open the workflow
            rk.force_update()
            rk.user_input('down', 'right')
            rk.wait_until_loaded(schd.tokens.id)

            # focus on a task
            rk.user_input('down', 'right', 'down', 'right')
            rk.compare_screenshot(
                # take a screenshot to ensure we have focused on the task
                # successfully
                'task-selected',
                'the cursor should be on the task 1/foo',
            )

            # focus on the hold mutation for a task
            rk.user_input('enter', 'down')
            rk.compare_screenshot(
                # take a screenshot to ensure we have focused on the mutation
                # successfully
                'hold-mutation-selected',
                'the cursor should be on the "hold" mutation',
            )

            # run the hold mutation
            rk.user_input('enter')

            # the mutation should be in the scheduler's command_queue
            await asyncio.sleep(0)
            assert log_filter(contains="hold(tasks=['1/one'])")

        # close the dialogue and re-run the hold mutation
        rk.user_input('q', 'q', 'enter')
        rk.compare_screenshot(
            'command-failed-workflow-stopped',
            'an error should be visible explaining that the operation'
            ' cannot be performed on a stopped workflow',
            # NOTE: don't update so Tui still thinks the workflow is running
            force_update=False,
        )

        # force mutations to raise ClientError
        def _get_client(*args, **kwargs):
            raise ClientError('mock error')
        monkeypatch.setattr(
            'cylc.flow.tui.data.get_client',
            _get_client,
        )

        # close the dialogue and re-run the hold mutation
        rk.user_input('q', 'q', 'enter')
        rk.compare_screenshot(
            'command-failed-client-error',
            'an error should be visible explaining that the operation'
            ' failed due to a client error',
            # NOTE: don't update so Tui still thinks the workflow is running
            force_update=False,
        )


@pytest.fixture
def standardise_cli_cmds(monkeypatch):
    """This remove the variable bit of the workflow ID from CLI commands.

    The workflow ID changes from run to run. In order to make screenshots
    stable, this
    """
    from cylc.flow.tui.data import extract_context

    def _extract_context(selection):
        context = extract_context(selection)
        if 'workflow' in context:
            context['workflow'] = [
                workflow.rsplit('/', 1)[-1]
                for workflow in context.get('workflow', [])
            ]
        return context
    monkeypatch.setattr(
        'cylc.flow.tui.data.extract_context',
        _extract_context,
    )


@pytest.fixture
def capture_commands(monkeypatch):
    ret = []
    returncode = [0]

    class _Popen:
        def __init__(self, *args, **kwargs):
            ret.append(args)

        def communicate(self):
            return 'mock-stdout', 'mock-stderr'

        @property
        def returncode(self):
            return returncode[0]

    monkeypatch.setattr(
        'cylc.flow.tui.data.Popen',
        _Popen,
    )

    return ret, returncode


async def test_offline_mutation(
    one_conf,
    flow,
    rakiura,
    capture_commands,
    standardise_cli_cmds,
):
    flow(one_conf, name='one')
    commands, returncode = capture_commands

    with rakiura(size='80,15') as rk:
        # run the stop-all mutation
        rk.wait_until_loaded('root')
        rk.user_input('enter', 'down')
        rk.compare_screenshot(
            # take a screenshot to ensure we have focused on the task
            # successfully
            'stop-all-mutation-selected',
            'the stop-all mutation should be selected',
        )
        rk.user_input('enter')

        # the command "cylc stop '*'" should have been run
        assert commands == [(['cylc', 'stop', '*'],)]
        commands.clear()

        # run the clean command on the workflow
        rk.user_input('down', 'enter', 'down')
        rk.compare_screenshot(
            # take a screenshot to ensure we have focused on the mutation
            # successfully
            'clean-mutation-selected',
            'the clean mutation should be selected',
        )
        rk.user_input('enter')

        # the command "cylc clean <id>" should have been run
        assert commands == [(['cylc', 'clean', '--yes', 'one'],)]
        commands.clear()

        # make commands fail
        returncode[:] = [1]
        rk.user_input('enter', 'down')
        rk.compare_screenshot(
            # take a screenshot to ensure we have focused on the mutation
            # successfully
            'clean-mutation-selected',
            'the clean mutation should be selected',
        )
        rk.user_input('enter')

        assert commands == [(['cylc', 'clean', '--yes', 'one'],)]

        rk.compare_screenshot(
            # take a screenshot to ensure we have focused on the mutation
            # successfully
            'clean-command-error',
            'there should be a box displaying the error containing the stderr'
            ' returned by the command',
        )


async def test_set_mutation(
    flow,
    scheduler,
    start,
    rakiura,
):
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a => z'
            },
        },
    }, name='one')
    schd = scheduler(id_)
    async with start(schd):
        await schd.update_data_structure()
        with rakiura(schd.tokens.id, size='80,15') as rk:
            # open the context menu on 1/a
            rk.user_input('down', 'down', 'down', 'enter')
            rk.force_update()

            # select the "set" mutation
            rk.user_input(*(('down',) * 7))  # 7th command down

            rk.compare_screenshot(
                # take a screenshot to ensure we have focused on the mutation
                # successfully
                'set-command-selected',
                'The command menu should be open for the task 1/a with the'
                ' set command selected.'
            )

            # issue the "set" mutation
            rk.user_input('enter')

            # wait for the command to be received and run it
            await process_command(schd)

            # close the error dialogue
            # NOTE: This hides an asyncio error that does not occur outside of
            #       the tests
            rk.user_input('q', 'q', 'q')

            rk.compare_screenshot(
                # take a screenshot to ensure we have focused on the mutation
                # successfully
                'task-state-updated',
                '1/a should now show as succeeded,'
                ' there should be no associated job.'
            )

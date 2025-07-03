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

from random import random

import pytest
import urwid

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.flow.task_state import (
    TASK_STATUS_EXPIRED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
)
from cylc.flow.tui.util import MODIFIER_ATTR_MAPPING
from cylc.flow.workflow_status import StopMode


def _add_xtrig(schd, itask, sig, label, satisfied=False):
    """Register a new xtrigger.

    This is enough to get the data store to reflect the xtrig, but don't expect
    it to be functional!
    """
    (
        schd.data_store_mgr.xtrigger_tasks
        .setdefault(sig, set())
        .add((itask.tokens.id, label))
    )
    schd.data_store_mgr.delta_xtrigger(sig, satisfied)


def set_task_state(schd, task_states):
    """Force tasks into the desired states.

    Task states should be of the format (cycle, task, state, is_held).
    """
    for cycle, task, state, modifiers in task_states:
        itask = schd.pool.get_task(cycle, task)
        if not itask:
            itask = schd.pool.spawn_task(task, cycle, {1})
        if modifiers.pop('is_retry', None):
            _add_xtrig(
                schd, itask, 'wall_clock(offset=0)', f'_cylc_retry_{random()}'
            )
        if modifiers.pop('is_wallclock', None):
            _add_xtrig(schd, itask, 'wall_clock(offset=1)', 'my_clock')
        if modifiers.pop('is_xtriggered', None):
            _add_xtrig(schd, itask, 'my_custom()', 'my_custom')
        itask.state_reset(state, **modifiers)
        schd.data_store_mgr.delta_task_state(itask)
        schd.data_store_mgr.increment_graph_window(
            itask.tokens,
            cycle,
            {1},
        )


async def test_tui_basics(rakiura):
    """Test basic Tui interaction with no workflows."""
    with rakiura(size='80,40') as rk:
        # the app should open
        rk.compare_screenshot('test-rakiura', 'the app should have loaded')

        # "h" should bring up the onscreen help
        rk.user_input('h')
        rk.compare_screenshot(
            'test-rakiura-help',
            'the help screen should be visible'
        )

        # "q" should close the popup
        rk.user_input('q')
        rk.compare_screenshot(
            'test-rakiura',
            'the help screen should have closed',
        )

        # "enter" should bring up the context menu
        rk.user_input('enter')
        rk.compare_screenshot(
            'test-rakiura-enter',
            'the context menu should have opened',
        )

        # "enter" again should close it via the "cancel" button
        rk.user_input('enter')
        rk.compare_screenshot(
            'test-rakiura',
            'the context menu should have closed',
        )

        # "ctrl d" should exit Tui
        with pytest.raises(urwid.ExitMainLoop):
            rk.user_input('ctrl d')

        # "q" should exit Tui
        with pytest.raises(urwid.ExitMainLoop):
            rk.user_input('q')


async def test_subscribe_unsubscribe(
    one_conf, flow, scheduler, start, rakiura
):
    """Test a simple workflow with one task."""
    id_ = flow(one_conf, name='one')
    schd = scheduler(id_)
    async with start(schd):
        await schd.update_data_structure()
        with rakiura(size='80,15') as rk:
            rk.compare_screenshot(
                'unsubscribed',
                'the workflow should be collapsed'
                ' (no subscription no state totals)',
            )

            # expand the workflow to subscribe to it
            rk.user_input('down', 'right')
            rk.wait_until_loaded()
            rk.compare_screenshot(
                'subscribed',
                'the workflow should be expanded',
            )

            # collapse the workflow to unsubscribe from it
            rk.user_input('left', 'up')
            rk.force_update()
            rk.compare_screenshot(
                'unsubscribed',
                'the workflow should be collapsed'
                ' (no subscription no state totals)',
            )


async def test_workflow_states(one_conf, flow, scheduler, start, rakiura):
    """Test viewing multiple workflows in different states."""
    # one => stopping
    id_1 = flow(one_conf, name='one')
    schd_1 = scheduler(id_1)
    # two => paused
    id_2 = flow(one_conf, name='two')
    schd_2 = scheduler(id_2)
    # tre => stopped
    flow(one_conf, name='tre')

    async with start(schd_1):
        schd_1.stop_mode = StopMode.AUTO  # make it look like we're stopping
        await schd_1.update_data_structure()

        async with start(schd_2):
            await schd_2.update_data_structure()
            with rakiura(size='80,15') as rk:
                rk.compare_screenshot(
                    'unfiltered',
                    'All workflows should be visible (one, two, tree)',
                )

                # filter for active workflows (i.e. paused, running, stopping)
                rk.user_input('p')
                rk.compare_screenshot(
                    'filter-active',
                    'Only active workflows should be visible (one, two)'
                )

                # invert the filter so we are filtering for stopped workflows
                rk.user_input('W', 'enter', 'q')
                rk.compare_screenshot(
                    'filter-stopped',
                    'Only stopped workflow should be visible (tre)'
                )

                # filter in paused workflows
                rk.user_input('W', 'down', 'enter', 'q')
                rk.force_update()
                rk.compare_screenshot(
                    'filter-stopped-or-paused',
                    'Only stopped or paused workflows should be visible'
                    ' (two, tre)',
                )

                # reset the state filters
                rk.user_input('W', 'down', 'down', 'enter', 'down', 'enter')

                # scroll to the id filter text box
                rk.user_input('down', 'down', 'down', 'down')

                # scroll to the end of the ID
                rk.user_input(*['right'] * (
                    len(schd_1.tokens['workflow'].rsplit('/', 1)[0]) + 1)
                )

                # type the letter "t"
                # (this should filter for workflows starting with "t")
                rk.user_input('t')
                rk.force_update()  # this is required for the tests
                rk.user_input('page up', 'q')  # close the dialogue

                rk.compare_screenshot(
                    'filter-starts-with-t',
                    'Only workflows starting with the letter "t" should be'
                    ' visible (two, tre)',
                )


async def test_task_states(flow, scheduler, start, rakiura):
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'true',
        },
        'scheduling': {
            'initial cycle point': '1',
            'cycling mode': 'integer',
            'runahead limit': 'P1',
            'graph': {
                'P1': '''
                    a & b & c
                '''
            },
        },
        'runtime': {
            'X': {},
            'Y': {},
            'Y1': {'inherit': 'Y'},
            'a': {'inherit': 'X'},
            'b': {'inherit': 'Y'},
            'c': {'inherit': 'Y1'},
        },
    }, name='test_task_states')
    schd = scheduler(id_)
    async with start(schd):
        set_task_state(
            schd,
            [
                (
                    IntegerPoint('1'),
                    'a',
                    TASK_STATUS_SUCCEEDED,
                    {'is_held': False}
                ),
                (
                    IntegerPoint('1'),
                    'b',
                    TASK_STATUS_FAILED,
                    {'is_held': False}
                ),
                (
                    IntegerPoint('1'),
                    'c',
                    TASK_STATUS_EXPIRED,
                    {'is_held': False}
                ),
                (
                    IntegerPoint('2'),
                    'a',
                    TASK_STATUS_SUBMITTED,
                    {'is_held': False}
                ),
                (
                    IntegerPoint('2'),
                    'b',
                    TASK_STATUS_RUNNING,
                    {'is_held': True}
                ),
                (
                    IntegerPoint('2'),
                    'c',
                    TASK_STATUS_SUBMIT_FAILED,
                    {'is_held': True}
                ),
            ]
        )
        await schd.update_data_structure()

        with rakiura(schd.tokens.id, size='80,30') as rk:
            rk.compare_screenshot(
                'unfiltered',
                'all tasks should be displayed'
                ' (i.e. 1/*, 2/* and 3/* should be displayed)',
            )

            # filter OUT waiting tasks
            rk.user_input('T', 'down', 'enter', 'q')  # select waiting
            rk.compare_screenshot(
                'filter-not-waiting',
                'waiting tasks should be filtered out'
                ' (i.e. 1/* and 2/* should be displayed)',
            )

            # filter OUT waiting & expired tasks
            rk.user_input('T', 'down', 'down', 'enter', 'q')  # select expired
            rk.compare_screenshot(
                'filter-not-waiting-or-expired',
                'waiting & expired tasks should be filtered out'
                ' (i.e. only 1/a, 1/b and 2/* should be displayed)',
            )

            # filter FOR waiting & expired tasks
            rk.user_input('T', 'enter', 'q')  # select invert
            rk.compare_screenshot(
                'filter-waiting-or-expired',
                'only waiting and expired tasks should be displayed'
                ' (i.e. only 1/c and 3/* should be displayed)',
            )

            # filter FOR submitted tasks (using shortcuts)
            rk.user_input('R', 's')  # reset filters and apply submitted filter
            rk.compare_screenshot(
                'filter-submitted',
                'only submitted tasks should be displayed'
                ' (i.e. only 2/a should be displayed)',
            )


async def test_task_modifiers(flow, scheduler, start, rakiura):
    """It should display task modifiers and text summaries of them."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '\n'.join(
                    modifier
                    for modifier, _ in MODIFIER_ATTR_MAPPING.values()
                ) + '\nall'
            },
        },
    }, name='test_task_modifiers')
    schd = scheduler(id_)
    async with start(schd):
        set_task_state(
            schd,
            [
                *[
                    (
                        IntegerPoint('1'),
                        modifier,
                        TASK_STATUS_WAITING,
                        # NOTE: set is_queued=False as the default because
                        # parentless tasks are autoqueued on startup
                        {**{'is_queued': False}, modifier: True},
                    )
                    for modifier, _ in MODIFIER_ATTR_MAPPING.values()
                ],
                (
                    IntegerPoint('1'),
                    'all',
                    TASK_STATUS_WAITING,
                    {
                        modifier: True
                        for modifier, _ in MODIFIER_ATTR_MAPPING.values()
                    },
                )
            ]
        )
        await schd.update_data_structure()

        with rakiura(schd.tokens.id, size='80,30') as rk:
            # test modifier icon rendering
            rk.compare_screenshot(
                'task-modifiers',
                'all tasks should be displayed along with their modifiers'
            )

            # test modifier text summary
            rk.user_input('down', 'down', 'down', 'enter')  # select task "all"
            rk.compare_screenshot(
                'task-context-menu',
                'all modifiers should be listed along with the task state'
                ' (i.e. the text "held, runahead, queued, retry scheduled,'
                ' wallclock, xtriggered") should be present'
            )


async def test_navigation(flow, scheduler, start, rakiura):
    """Test navigating with the arrow keys."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'A & B1 & B2',
            }
        },
        'runtime': {
            'A': {},
            'B': {},
            'B1': {'inherit': 'B'},
            'B2': {'inherit': 'B'},
            'a1': {'inherit': 'A'},
            'a2': {'inherit': 'A'},
            'b11': {'inherit': 'B1'},
            'b12': {'inherit': 'B1'},
            'b21': {'inherit': 'B2'},
            'b22': {'inherit': 'B2'},
        }
    }, name='one')
    schd = scheduler(id_)
    async with start(schd):
        await schd.update_data_structure()

        with rakiura(size='80,30') as rk:
            # wait for the workflow to appear (collapsed)
            rk.wait_until_loaded('#spring')

            rk.compare_screenshot(
                'on-load',
                'the workflow should be collapsed when Tui is loaded',
            )

            # pressing "right" should connect to the workflow
            # and expand it once the data arrives
            rk.user_input('down', 'right')
            rk.wait_until_loaded(schd.tokens.id)
            rk.compare_screenshot(
                'workflow-expanded',
                'the workflow should be expanded',
            )

            # pressing "left" should collapse the node
            rk.user_input('down', 'down', 'left')
            rk.compare_screenshot(
                'family-A-collapsed',
                'the family "1/A" should be collapsed',
            )

            # the "page up" and "page down" buttons should navigate to the top
            # and bottom of the screen
            rk.user_input('page down')
            rk.compare_screenshot(
                'cursor-at-bottom-of-screen',
                'the cursor should be at the bottom of the screen',
            )


async def test_auto_expansion(flow, scheduler, start, rakiura):
    """It should automatically expand cycles and top-level families.

    When a workflow is expanded, Tui should auto expand cycles and top-level
    families. Any new cycles and top-level families should be auto-expanded
    when added.
    """
    id_ = flow({
        'scheduling': {
            'runahead limit': 'P1',
            'initial cycle point': '1',
            'cycling mode': 'integer',
            'graph': {
                'P1': 'b[-P1] => a => b'
            },
        },
        'runtime': {
            'A': {},
            'a': {'inherit': 'A'},
            'b': {},
        },
    }, name='one')
    schd = scheduler(id_)
    with rakiura(size='80,20') as rk:
        async with start(schd):
            await schd.update_data_structure()
            # wait for the workflow to appear (collapsed)
            rk.wait_until_loaded('#spring')

            # open the workflow
            rk.force_update()
            rk.user_input('down', 'right')
            rk.wait_until_loaded(schd.tokens.id)

            rk.compare_screenshot(
                'on-load',
                'cycle "1" and top-level family "1/A" should be expanded',
            )
            for task in ('a', 'b'):
                schd.pool.set_prereqs_and_outputs(
                    items=[f"1/{task}"],
                    outputs=[TASK_OUTPUT_SUCCEEDED],
                    prereqs=[],
                    flow=[]
                )

            await schd.update_data_structure()
            schd.update_data_store()

            rk.compare_screenshot(
                'later-time',
                'cycle "2" and top-level family "2/A" should be expanded',
            )


async def test_restart_reconnect(one_conf, flow, scheduler, start, rakiura):
    """It should handle workflow shutdown and restart.

    The Cylc client can raise exceptions e.g. WorkflowStopped. Any text written
    to stdout/err will mess with Tui. The purpose of this test is to ensure Tui
    can handle shutdown / restart without any errors occuring and any spurious
    text appearing on the screen.
    """
    with rakiura(size='80,20') as rk:
        schd = scheduler(flow(one_conf, name='one'))

        # 1- start the workflow
        async with start(schd):
            await schd.update_data_structure()
            # wait for the workflow to appear (collapsed)
            rk.wait_until_loaded('#spring')

            # expand the workflow (subscribes to updates from it)
            rk.force_update()
            rk.user_input('down', 'right')

            # wait for workflow to appear (expanded)
            rk.wait_until_loaded(schd.tokens.id)
            rk.compare_screenshot(
                '1-workflow-running',
                'the workflow should appear in tui and be expanded',
            )

        # 2 - stop the worlflow
        rk.compare_screenshot(
            '2-workflow-stopped',
            'the stopped workflow should be collapsed with a message saying'
            ' workflow stopped',
        )

        # 3- restart the workflow
        schd = scheduler(flow(one_conf, name='one'))
        async with start(schd):
            await schd.update_data_structure()
            rk.wait_until_loaded(schd.tokens.id)
            rk.compare_screenshot(
                '3-workflow-restarted',
                'the restarted workflow should be expanded',
            )


async def test_states(flow, scheduler, start, rakiura):
    """It should dim no-flow tasks and display state summary in context menus.
    """
    id_ = flow(
        {
            'scheduling': {
                'graph': {
                    'R1': 'a & b & c',
                },
            },
        },
        name='one',
    )
    from cylc.flow.scheduler import Scheduler
    schd: Scheduler = scheduler(id_)

    async with start(schd):
        a = schd.pool.get_task(IntegerPoint('1'), 'a')
        b = schd.pool.get_task(IntegerPoint('1'), 'b')
        c = schd.pool.get_task(IntegerPoint('1'), 'c')
        assert a and b and c

        # set task flow numbers
        assert a.flow_nums == {1}
        b.flow_nums = {1, 2}
        c.flow_nums = {}

        # set task state
        a.state_reset(TASK_STATUS_SUCCEEDED, is_held=True)
        b.state_reset(TASK_STATUS_WAITING, is_queued=True)
        c.state_reset(TASK_STATUS_WAITING, is_queued=False, is_runahead=True)

        # update data store
        for task in (a, b, c):
            schd.data_store_mgr.delta_task_state(task)
            schd.data_store_mgr.delta_task_flow_nums(task)
        await schd.update_data_structure()

        with rakiura(schd.tokens.id, size='80,15') as rk:
            rk.compare_screenshot(
                'on-load',
                'the workflow should be expanded,'
                ' no-flow task 1/c should be dimmed'
            )

            # workflow node
            rk.user_input('down', 'enter')
            rk.compare_screenshot(
                'workflow-context--paused',
                'the workflow should show as paused in the context menu',
            )

            # cycle: 1
            rk.user_input('q', 'down', 'enter')
            rk.compare_screenshot(
                'cycle-context--waiting',
                'the cycle should show as waiting in the context menu'
            )

            # task:a
            rk.user_input('q', 'down', 'enter')
            rk.compare_screenshot(
                'task-context--succeeded+held',
                'the task should show as succeeded+held in the context menu,'
                ' no flow numbers should be displayed',
            )

            # task:b
            rk.user_input('q', 'down', 'enter')
            rk.compare_screenshot(
                'task-context--waiting+queued',
                'the task should show as waiting+queued in the context menu,'
                ' the flow numbers 1,2 should be displayed',
            )

            # task:c
            rk.user_input('q', 'down', 'enter')
            rk.compare_screenshot(
                'task-context--waiting+runahead',
                'the task should show as waiting+runahead in the context menu,'
                ' the task should be marked as flows=None'
            )

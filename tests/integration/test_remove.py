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

import logging
import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.commands import (
    force_trigger_tasks,
    reload_workflow,
    remove_tasks,
    run_cmd,
)
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import TASK_STATUS_FAILED


@pytest.fixture
async def cylc_show_prereqs(cylc_show):
    """Fixture that returns the prereq info from `cylc show` in an
    easy-to-use format."""
    async def inner(schd: Scheduler, task: str):
        prerequisites = (await cylc_show(schd, task))[task]['prerequisites']
        return [
            (
                p['satisfied'],
                {c['taskId']: c['satisfied'] for c in p['conditions']},
            )
            for p in prerequisites
        ]

    return inner


@pytest.fixture
def example_workflow(flow):
    return flow({
        'scheduling': {
            'graph': {
                # Note: test both `&` and separate arrows for combining
                # dependencies
                'R1': '''
                    a1 & a2 => b
                    a3 => b
                ''',
            },
        },
    })


def get_data_store_flow_nums(schd: Scheduler, itask: TaskProxy):
    _, ds_tproxy = schd.data_store_mgr.store_node_fetcher(itask.tokens)
    if ds_tproxy:
        return ds_tproxy.flow_nums


async def test_basic(
    example_workflow, scheduler, start, db_select
):
    """Test removing a task from all flows."""
    schd: Scheduler = scheduler(example_workflow)
    async with start(schd):
        a1 = schd.pool._get_task_by_id('1/a1')
        a3 = schd.pool._get_task_by_id('1/a3')
        schd.pool.spawn_on_output(a1, TASK_OUTPUT_SUCCEEDED)
        schd.pool.spawn_on_output(a3, TASK_OUTPUT_SUCCEEDED)
        await schd.update_data_structure()

        assert a1 in schd.pool.get_tasks()
        for table in ('task_states', 'task_outputs'):
            assert db_select(schd, True, table, 'flow_nums', name='a1') == [
                ('[1]',),
            ]
        assert db_select(
            schd, True, 'task_prerequisites', 'satisfied', prereq_name='a1'
        ) == [
            ('satisfied naturally',),
        ]
        assert get_data_store_flow_nums(schd, a1) == '[1]'

        await run_cmd(remove_tasks(schd, ['1/a1'], []))
        await schd.update_data_structure()

        assert a1 not in schd.pool.get_tasks()  # removed from pool
        for table in ('task_states', 'task_outputs'):
            assert db_select(schd, True, table, 'flow_nums', name='a1') == [
                ('[]',),  # removed from all flows
            ]
        assert db_select(
            schd, True, 'task_prerequisites', 'satisfied', prereq_name='a1'
        ) == [
            ('0',),  # prereq is now unsatisfied
        ]
        assert get_data_store_flow_nums(schd, a1) == '[]'


async def test_specific_flow(
    example_workflow, scheduler, start, db_select
):
    """Test removing a task from a specific flow."""
    schd: Scheduler = scheduler(example_workflow)

    def select_prereqs():
        return db_select(
            schd,
            True,
            'task_prerequisites',
            'flow_nums',
            'satisfied',
            prereq_name='a1',
        )

    async with start(schd):
        a1 = schd.pool._get_task_by_id('1/a1')
        await run_cmd(force_trigger_tasks(schd, ['1/a1'], ['1', '2']))
        schd.pool.spawn_on_output(a1, TASK_OUTPUT_SUCCEEDED)
        await schd.update_data_structure()

        assert a1 in schd.pool.get_tasks()
        assert a1.flow_nums == {1, 2}
        for table in ('task_states', 'task_outputs'):
            assert sorted(
                db_select(schd, True, table, 'flow_nums', name='a1')
            ) == [
                ('[1, 2]',),  # triggered task
                ('[1]',),  # original spawned task
            ]
        assert select_prereqs() == [
            ('[1, 2]', 'satisfied naturally'),
        ]
        assert get_data_store_flow_nums(schd, a1) == '[1, 2]'

        await run_cmd(remove_tasks(schd, ['1/a1'], ['1']))
        await schd.update_data_structure()

        assert a1 in schd.pool.get_tasks()  # still in pool
        assert a1.flow_nums == {2}
        for table in ('task_states', 'task_outputs'):
            assert sorted(
                db_select(schd, True, table, 'flow_nums', name='a1')
            ) == [
                ('[2]',),
                ('[]',),
            ]
        assert select_prereqs() == [
            ('[1, 2]', '0'),
        ]
        assert get_data_store_flow_nums(schd, a1) == '[2]'


async def test_unset_prereq(example_workflow, scheduler, start):
    """Test removing a task unsets any prerequisites it satisfied."""
    schd: Scheduler = scheduler(example_workflow)
    async with start(schd):
        for task in ('a1', 'a2', 'a3'):
            schd.pool.spawn_on_output(
                schd.pool.get_task(IntegerPoint('1'), task),
                TASK_OUTPUT_SUCCEEDED,
            )
        b = schd.pool.get_task(IntegerPoint('1'), 'b')
        assert b.prereqs_are_satisfied()

        await run_cmd(remove_tasks(schd, ['1/a1'], []))

        assert not b.prereqs_are_satisfied()


async def test_not_unset_prereq(
    example_workflow, scheduler, start, db_select
):
    """Test removing a task does not unset a force-satisfied prerequisite
    (one that was satisfied by `cylc set --pre`)."""
    schd: Scheduler = scheduler(example_workflow)
    async with start(schd):
        # This set prereq should not be unset by removing a1:
        schd.pool.set_prereqs_and_outputs(
            ['1/b'], outputs=[], prereqs=['1/a1'], flow=[]
        )
        # Whereas the prereq satisfied by this set output *should* be unset
        # by removing a2:
        schd.pool.set_prereqs_and_outputs(
            ['1/a2'], outputs=['succeeded'], prereqs=[], flow=[]
        )
        await schd.update_data_structure()

        assert sorted(
            db_select(
                schd, True, 'task_prerequisites', 'prereq_name', 'satisfied'
            )
        ) == [
            ('a1', 'force satisfied'),
            ('a2', 'satisfied naturally'),
            ('a3', '0'),
        ]

        await run_cmd(remove_tasks(schd, ['1/a1', '1/a2'], []))
        await schd.update_data_structure()

        assert sorted(
            db_select(
                schd, True, 'task_prerequisites', 'prereq_name', 'satisfied'
            )
        ) == [
            ('a1', 'force satisfied'),
            ('a2', '0'),
            ('a3', '0'),
        ]


async def test_nothing_to_do(
    example_workflow, scheduler, start, log_filter
):
    """Test removing an invalid task."""
    schd: Scheduler = scheduler(example_workflow)
    async with start(schd):
        await run_cmd(remove_tasks(schd, ['1/doh'], []))
    assert log_filter(logging.WARNING, "No matching tasks found: doh")


async def test_logging(
    flow, scheduler, start, log_filter, caplog: pytest.LogCaptureFixture
):
    """Test logging of a mixture of valid and invalid task removals."""
    schd: Scheduler = scheduler(
        flow({
            'scheduler': {
                'cycle point format': 'CCYY',
            },
            'scheduling': {
                'initial cycle point': '2000',
                'graph': {
                    'R3//P1Y': 'b[-P1Y] => a & b',
                },
            },
        })
    )
    tasks_to_remove = [
        # Active, removable tasks:
        '2000/*',
        # Future, non-removable tasks:
        '2001/a', '2001/b',
        # Glob that doesn't match any active tasks:
        '2002/*',
        # Invalid tasks:
        '2005/a', '2000/doh',
    ]
    async with start(schd) as log:
        log.set_level(logging.DEBUG, CYLC_LOG)
        await run_cmd(remove_tasks(schd, tasks_to_remove, []))

    assert log_filter(
        logging.INFO, "Removed tasks: 2000/a (flows=1), 2000/b (flows=1)"
    )

    assert log_filter(logging.DEBUG, "Task(s) not removable: 2001/a, 2001/b")
    assert log_filter(logging.WARNING, "No active tasks matching: 2002/*")
    assert log_filter(logging.WARNING, "Invalid cycle point for task: a, 2005")
    assert log_filter(logging.WARNING, "No matching tasks found: doh")
    # No tasks were submitted/running so none should have been killed:
    assert "job killed" not in caplog.text


async def test_logging_flow_nums(
    example_workflow, scheduler, start, log_filter
):
    """Test logging of task removals involving flow numbers."""
    schd: Scheduler = scheduler(example_workflow)
    async with start(schd) as log:
        log.set_level(logging.DEBUG, CYLC_LOG)
        await run_cmd(force_trigger_tasks(schd, ['1/a1'], ['1', '2']))
        # Removing from flow that doesn't exist doesn't work:
        await run_cmd(remove_tasks(schd, ['1/a1'], ['3']))
        assert log_filter(
            logging.DEBUG, "Task(s) not removable: 1/a1 (flows=3)"
        )

        # But if a valid flow is included, it will be removed from that flow:
        await run_cmd(remove_tasks(schd, ['1/a1'], ['2', '3']))
        assert log_filter(logging.INFO, "Removed tasks: 1/a1 (flows=2)")
        assert schd.pool._get_task_by_id('1/a1').flow_nums == {1}


async def test_retrigger(flow, scheduler, run, reflog, complete):
    """Test prereqs & re-run behaviour when removing tasks."""
    schd: Scheduler = scheduler(
        flow('a => b => c'),
        paused_start=False,
    )
    async with run(schd):
        reflog_triggers: set = reflog(schd)
        await complete(schd, '1/b')

        await run_cmd(remove_tasks(schd, ['1/a', '1/b'], []))
        schd.process_workflow_db_queue()
        # Removing 1/b should un-queue 1/c:
        assert len(schd.pool.task_queue_mgr.queues['default'].deque) == 0

        assert reflog_triggers == {
            ('1/a', None),
            ('1/b', ('1/a',)),
        }
        reflog_triggers.clear()

        await run_cmd(force_trigger_tasks(schd, ['1/a'], []))
        await complete(schd)

    assert reflog_triggers == {
        ('1/a', None),
        # 1/b should have run again after 1/a on the re-trigger in flow 1:
        ('1/b', ('1/a',)),
        ('1/c', ('1/b',)),
    }


async def test_prereqs(
    flow, scheduler, run, complete, cylc_show_prereqs, log_filter
):
    """Test prereqs & stall behaviour when removing tasks."""
    schd: Scheduler = scheduler(
        flow('(a1 | a2) & b => x'),
        paused_start=False,
    )
    async with run(schd):
        await complete(schd, '1/a1', '1/a2', '1/b')

        await run_cmd(remove_tasks(schd, ['1/a1'], []))
        assert not schd.pool.is_stalled()
        assert len(schd.pool.task_queue_mgr.queues['default'].deque)
        # `cylc show` should reflect the now-unsatisfied condition:
        assert await cylc_show_prereqs(schd, '1/x') == [
            (True, {'1/a1': False, '1/a2': True, '1/b': True})
        ]

        await run_cmd(remove_tasks(schd, ['1/b'], []))
        # Should cause stall now because 1/c prereq is unsatisfied:
        assert len(schd.pool.task_queue_mgr.queues['default'].deque) == 0
        assert schd.pool.is_stalled()
        assert log_filter(
            logging.WARNING,
            "1/x is waiting on ['1/a1:succeeded', '1/b:succeeded']",
        )
        assert await cylc_show_prereqs(schd, '1/x') == [
            (False, {'1/a1': False, '1/a2': True, '1/b': False})
        ]

        assert schd.pool._get_task_by_id('1/x')
        await run_cmd(remove_tasks(schd, ['1/a2'], []))
        # Should cause 1/x to be removed from the pool as it no longer has
        # any satisfied prerequisite tasks:
        assert not schd.pool._get_task_by_id('1/x')
        assert log_filter(
            logging.INFO,
            regex=r"1/x.* removed .* prerequisite task\(s\) removed",
        )


async def test_downstream_preparing(flow, scheduler, start):
    """Downstream dependents should not be removed if they are already
    preparing."""
    schd: Scheduler = scheduler(
        flow('''
            a => x
            a => y
        '''),
    )
    async with start(schd):
        a = schd.pool._get_task_by_id('1/a')
        schd.pool.spawn_on_output(a, TASK_OUTPUT_SUCCEEDED)
        assert schd.pool.get_task_ids() == {'1/a', '1/x', '1/y'}

        schd.pool._get_task_by_id('1/y').state_reset('preparing')
        await run_cmd(remove_tasks(schd, ['1/a'], []))
        assert schd.pool.get_task_ids() == {'1/y'}


async def test_downstream_other_flows(flow, scheduler, run, complete):
    """Downstream dependents should not be removed if they exist in other
    flows."""
    schd: Scheduler = scheduler(
        flow('''
            a => b => c => x
            a => x
        '''),
        paused_start=False,
    )
    async with run(schd):
        await complete(schd, '1/a')
        await run_cmd(force_trigger_tasks(schd, ['1/c'], ['2']))
        c = schd.pool._get_task_by_id('1/c')
        schd.pool.spawn_on_output(c, TASK_OUTPUT_SUCCEEDED)
        assert schd.pool._get_task_by_id('1/x').flow_nums == {1, 2}

        await run_cmd(remove_tasks(schd, ['1/c'], ['2']))
        assert schd.pool.get_task_ids() == {'1/b', '1/x'}
        # Note: in future we might want to remove 1/x from flow 2 as well, to
        # maintain flow continuity. However it is tricky at the moment because
        # other prerequisite tasks could exist in flow 2 (we don't know as
        # prereqs do not hold flow info other than in the DB).
        assert schd.pool._get_task_by_id('1/x').flow_nums == {1, 2}


async def test_suicide(flow, scheduler, run, reflog, complete):
    """Test that suicide prereqs are unset by `cylc remove`."""
    schd: Scheduler = scheduler(
        flow('''
            a => b => c => d => x
            a & c => !x
        '''),
        paused_start=False,
    )
    async with run(schd):
        reflog_triggers: set = reflog(schd)
        await complete(schd, '1/b')
        await run_cmd(remove_tasks(schd, ['1/a'], []))
        await complete(schd)

    assert reflog_triggers == {
        ('1/a', None),
        ('1/b', ('1/a',)),
        ('1/c', ('1/b',)),
        ('1/d', ('1/c',)),
        # 1/x not suicided as 1/a was removed:
        ('1/x', ('1/d',)),
    }


async def test_kill_running(flow, scheduler, run, complete, reflog):
    """Test removing a running task should kill it.

    Note this only tests simulation mode and a separate test for live mode
    exists in tests/functional/cylc-remove.
    """
    schd: Scheduler = scheduler(
        flow({
            'scheduling': {
                'graph': {
                    'R1': '''
                        a:started => b => c
                        a:failed => q
                    '''
                },
            },
            'runtime': {
                'a': {
                    'simulation': {
                        'default run length': 'PT30S'
                    },
                },
            },
        }),
        paused_start=False,
    )
    async with run(schd):
        reflog_triggers = reflog(schd)
        await complete(schd, '1/b')
        a = schd.pool._get_task_by_id('1/a')
        await run_cmd(remove_tasks(schd, ['1/a'], []))
        assert a.state(TASK_STATUS_FAILED, is_held=True)
        await complete(schd)

    assert reflog_triggers == {
        ('1/a', None),
        ('1/b', ('1/a',)),
        ('1/c', ('1/b',)),
        # The a:failed output should not cause 1/q to run
    }


async def test_reload_changed_config(flow, scheduler, run, complete):
    """Test that a task is removed from the pool if its configuration changes
    to make it no longer match the graph."""
    wid = flow({
        'scheduling': {
            'graph': {
                'R1': '''
                    a => b
                    a:started => s & b
                ''',
            },
        },
        'runtime': {
            'a': {
                'simulation': {
                    # Ensure 1/a still in pool during reload
                    'fail cycle points': 'all',
                },
            },
        },
    })
    schd: Scheduler = scheduler(wid, paused_start=False)
    async with run(schd):
        await complete(schd, '1/s')
        # Change graph then reload
        flow('b', workflow_id=wid)
        await run_cmd(reload_workflow(schd))
        assert schd.config.cfg['scheduling']['graph']['R1'] == 'b'
        assert schd.pool.get_task_ids() == {'1/a', '1/b'}

        await run_cmd(remove_tasks(schd, ['1/a'], []))
        await complete(schd, '1/b')

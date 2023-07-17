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

from copy import deepcopy
import logging
from typing import AsyncGenerator, Callable, Iterable, List, Tuple, Union

import pytest
from pytest import param

from cylc.flow import CYLC_LOG
from cylc.flow.cycling import PointBase
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.data_store_mgr import TASK_PROXIES
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.flow.scheduler import Scheduler
from cylc.flow.flow_mgr import FLOW_ALL
from cylc.flow.task_state import (
    TASK_STATUS_WAITING,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
)

# NOTE: foo and bar have no parents so at start-up (even with the workflow
# paused) they get spawned out to the runahead limit. 2/pub spawns
# immediately too, because we spawn autospawn absolute-triggered tasks as
# well as parentless tasks. 3/asd does not spawn at start, however.
EXAMPLE_FLOW_CFG = {
    'scheduler': {
        'allow implicit tasks': True
    },
    'scheduling': {
        'cycling mode': 'integer',
        'initial cycle point': 1,
        'final cycle point': 10,
        'runahead limit': 'P3',
        'graph': {
            'P1': 'foo & bar',
            'R1/2': 'foo[1] => pub',
            'R1/3': 'foo[-P1] => asd'
        }
    },
    'runtime': {
        'FAM': {},
        'bar': {'inherit': 'FAM'}
    }
}


def get_task_ids(
    name_point_list: Iterable[Tuple[str, Union[PointBase, str, int]]]
) -> List[str]:
    """Helper function to return sorted task identities
    from a list of  (name, point) tuples."""
    return sorted(f'{point}/{name}' for name, point in name_point_list)


def assert_expected_log(
    caplog_instance: pytest.LogCaptureFixture,
    expected_log_substrings: List[str]
) -> List[str]:
    """Helper function to check that expected (substrings of) log messages
    are actually in the log.

    Returns the list of actual logged messages.

    Args:
        caplog_instance: The instance of the caplog fixture for the particular
            test.
        expected_log_substrings: The expected, possibly partial, log messages.
    """
    logged_messages = [i[2] for i in caplog_instance.record_tuples]
    assert len(logged_messages) == len(expected_log_substrings)
    for actual, expected in zip(
            sorted(logged_messages), sorted(expected_log_substrings)):
        assert expected in actual
    return logged_messages


@pytest.fixture(scope='module')
async def mod_example_flow(
    mod_flow: Callable, mod_scheduler: Callable, mod_run: Callable
) -> Scheduler:
    """Return a scheduler for interrogating its task pool.

    This is module-scoped so faster than example_flow, but should only be used
    where the test does not mutate the state of the scheduler or task pool.
    """
    id_ = mod_flow(EXAMPLE_FLOW_CFG)
    schd: Scheduler = mod_scheduler(id_, paused_start=True)
    async with mod_run(schd):
        pass
    return schd


@pytest.fixture
async def example_flow(
    flow: Callable,
    scheduler: Callable,
    start,
    caplog: pytest.LogCaptureFixture,
) -> AsyncGenerator[Scheduler, None]:
    """Return a scheduler for interrogating its task pool.

    This is function-scoped so slower than mod_example_flow; only use this
    when the test mutates the scheduler or task pool.
    """
    # The run(schd) fixture doesn't work for modifying the DB, so have to
    # set up caplog and do schd.install()/.initialise()/.configure() instead
    caplog.set_level(logging.INFO, CYLC_LOG)
    id_ = flow(EXAMPLE_FLOW_CFG)
    schd: Scheduler = scheduler(id_)
    async with start(schd):
        yield schd


@pytest.mark.parametrize(
    'items, expected_task_ids, expected_bad_items, expected_warnings',
    [
        param(
            ['*/foo'], ['1/foo', '2/foo', '3/foo', '4/foo', '5/foo'], [], [],
            id="Point glob"
        ),
        param(
            ['1/*'],
            ['1/foo', '1/bar'], [], [],
            id="Name glob"
        ),
        param(
            ['1/FAM'], ['1/bar'], [], [],
            id="Family name"
        ),
        param(
            ['*:waiting'],
            ['1/foo', '1/bar', '2/foo', '2/bar', '2/pub', '3/foo', '3/bar',
             '4/foo', '4/bar', '5/foo', '5/bar'], [], [],
            id="Task state"
        ),
        param(
            ['8/foo', '3/asd'], [], ['8/foo', '3/asd'],
            [f"No active tasks matching: {x}" for x in ['8/foo', '3/asd']],
            id="Task not yet spawned"
        ),
        param(
            ['1/foo', '8/bar'], ['1/foo'], ['8/bar'],
            ["No active tasks matching: 8/bar"],
            id="Multiple items"
        ),
        param(
            ['1/grogu', '*/grogu'], [], ['1/grogu', '*/grogu'],
            [f"No active tasks matching: {x}" for x in ['1/grogu', '*/grogu']],
            id="No such task"
        ),
        param(
            ['*'],
            ['1/foo', '1/bar', '2/foo', '2/bar', '2/pub', '3/foo', '3/bar',
             '4/foo', '4/bar', '5/foo', '5/bar'], [], [],
            id="Glob everything"
        )
    ]
)
async def test_filter_task_proxies(
    items: List[str],
    expected_task_ids: List[str],
    expected_bad_items: List[str],
    expected_warnings: List[str],
    mod_example_flow: Scheduler,
    caplog: pytest.LogCaptureFixture
) -> None:
    """Test TaskPool.filter_task_proxies().

    The NOTE before EXAMPLE_FLOW_CFG above explains which tasks should be
    expected for the tests here.

    Params:
        items: Arg passed to filter_task_proxies().
        expected_task_ids: IDs of the TaskProxys that are expected to be
            returned.
        expected_bad_items: Expected to be returned.
        expected_warnings: Expected to be logged.
    """
    caplog.set_level(logging.WARNING, CYLC_LOG)
    task_pool = mod_example_flow.pool
    itasks, _, bad_items = task_pool.filter_task_proxies(items)
    task_ids = [itask.identity for itask in itasks]
    assert sorted(task_ids) == sorted(expected_task_ids)
    assert sorted(bad_items) == sorted(expected_bad_items)
    assert_expected_log(caplog, expected_warnings)


@pytest.mark.parametrize(
    'items, expected_task_ids, expected_bad_items, expected_warnings',
    [
        param(
            ['*:waiting'],
            ['1/waz', '1/foo', '1/bar', '2/foo', '2/bar', '2/pub', '3/foo',
             '3/bar', '4/foo', '4/bar', '5/foo', '5/bar'], [], [],
            id="Task state"
        ),
    ]
)
async def test_filter_task_proxies_hidden(
    items: List[str],
    expected_task_ids: List[str],
    expected_bad_items: List[str],
    expected_warnings: List[str],
    mod_example_flow: Scheduler,
    caplog: pytest.LogCaptureFixture
) -> None:
    """Test TaskPool.filter_task_proxies().

    This is the same as test_filter_task_proxies except we artificially add a
    new proxy "1/waz" to the hidden pool. Filtering should find a single copy
    each of the hidden and main pool tasks.

    See GitHub #4909: a bug in filtering was doubling up tasks in cycle points
    that appeared in both pools.

    The NOTE before EXAMPLE_FLOW_CFG above explains which tasks should be
    expected for the tests here.

    Params:
        items: Arg passed to filter_task_proxies().
        expected_task_ids: IDs of the TaskProxys that are expected to be
            returned, of the form "{point}/{name}"/
        expected_bad_items: Expected to be returned.
        expected_warnings: Expected to be logged.
    """
    caplog.set_level(logging.WARNING, CYLC_LOG)
    task_pool = mod_example_flow.pool

    # Duplicate a task proxy, rename it, and add it to the hidden pool.
    a_task = deepcopy(task_pool.get_tasks()[0])
    a_task.identity = "1/waz"
    task_pool.hidden_pool.setdefault(a_task.point, {})
    task_pool.hidden_pool[a_task.point][a_task.identity] = a_task

    itasks, _, bad_items = task_pool.filter_task_proxies(items)
    task_ids = [itask.identity for itask in itasks]
    assert sorted(task_ids) == sorted(expected_task_ids)
    assert sorted(bad_items) == sorted(expected_bad_items)
    assert_expected_log(caplog, expected_warnings)


@pytest.mark.parametrize(
    'items, expected_task_ids, expected_warnings',
    [
        param(
            ['4/foo'], ['4/foo'], [],
            id="Basic"
        ),
        param(
            ['3/*', '1/f*'], ['3/foo', '3/bar', '3/asd', '1/foo'], [],
            id="Name glob"
        ),
        param(
            ['3'], ['3/foo', '3/bar', '3/asd'], [],
            id="No name"
        ),
        param(
            ['2/FAM'], ['2/bar'], [],
            id="Family name"
        ),
        param(
            ['*/foo'], [], ["No matching tasks found: */foo"],
            id="Point glob not allowed"
        ),
        param(
            ['1/grogu', '1/gro*'], [],
            [f"No matching tasks found: {x}" for x in ['1/grogu', '1/gro*']],
            id="No such task"
        ),
        param(
            ['4/foo', '2/bar', '1/grogu'], ['4/foo', '2/bar'],
            ["No matching tasks found: 1/grogu"],
            id="Multiple items"
        ),
        param(
            ['20/foo', '1/pub'], [],
            ["Invalid cycle point for task: foo, 20",
             "Invalid cycle point for task: pub, 1"],
            id="Task not in graph at given cycle point"
        ),
        param(
            ['1/foo:badger'], ['1/foo'], [],
            id="Task state is ignored"
        ),
        param([], [], [], id="No items given")
    ]
)
async def test_match_taskdefs(
    items: List[str],
    expected_task_ids: List[str],
    expected_warnings: List[str],
    mod_example_flow: Scheduler,
    caplog: pytest.LogCaptureFixture
) -> None:
    """Test TaskPool.match_taskdefs().

    This looks for taskdefs at their valid cycle points, not the task pool.

    Params:
        items: Arg passed to match_taskdefs().
        ignore_state: Arg passed to match_taskdefs().
        expected_task_ids: Expected IDs of the tasks in the dict that gets
            returned, of the form "{point}/{name}".
        expected_warnings: Expected to be logged.
    """
    caplog.set_level(logging.WARNING, CYLC_LOG)
    task_pool = mod_example_flow.pool

    n_warnings, task_items = task_pool.match_taskdefs(items)
    assert get_task_ids(task_items) == sorted(expected_task_ids)

    logged_warnings = assert_expected_log(caplog, expected_warnings)
    assert n_warnings == len(logged_warnings)


@pytest.mark.parametrize(
    'items, expected_tasks_to_hold_ids, expected_warnings',
    [
        param(
            ['1/foo', '3/asd'], ['1/foo', '3/asd'], [],
            id="Active & future tasks"
        ),
        param(
            ['1/*', '2/*', '3/*', '6/*'],
            ['1/foo', '1/bar', '2/foo', '2/bar', '2/pub', '3/foo', '3/bar'],
            ["No active tasks matching: 6/*"],
            id="Name globs hold active tasks only"  # (active means n=0 here)
        ),
        param(
            ['1/FAM', '2/FAM', '6/FAM'], ['1/bar', '2/bar'],
            ["No active tasks in the family FAM matching: 6/FAM"],
            id="Family names hold active tasks only"
        ),
        param(
            ['1/grogu', 'H/foo', '20/foo', '1/pub'], [],
            ["No matching tasks found: grogu",
             "H/foo - invalid cycle point: H",
             "Invalid cycle point for task: foo, 20",
             "Invalid cycle point for task: pub, 1"],
            id="Non-existent task name or invalid cycle point"
        ),
        param(
            ['1/foo:waiting', '1/foo:failed', '6/bar:waiting'], ['1/foo'],
            ["No active tasks matching: 1/foo:failed",
             "No active tasks matching: 6/bar:waiting"],
            id="Specifying task state works for active tasks, not future tasks"
        )
    ]
)
async def test_hold_tasks(
    items: List[str],
    expected_tasks_to_hold_ids: List[str],
    expected_warnings: List[str],
    example_flow: Scheduler, caplog: pytest.LogCaptureFixture,
    db_select: Callable
) -> None:
    """Test TaskPool.hold_tasks().

    Also tests TaskPool_explicit_match_tasks_to_hold() in the process;
    kills 2 birds with 1 stone.

    Params:
        items: Arg passed to hold_tasks().
        expected_tasks_to_hold_ids: Expected IDs of the tasks that get put in
            the TaskPool.tasks_to_hold set, of the form "{point}/{name}"/
        expected_warnings: Expected to be logged.
    """
    expected_tasks_to_hold_ids = sorted(expected_tasks_to_hold_ids)
    caplog.set_level(logging.WARNING, CYLC_LOG)
    task_pool = example_flow.pool
    n_warnings = task_pool.hold_tasks(items)

    for itask in task_pool.get_all_tasks():
        hold_expected = itask.identity in expected_tasks_to_hold_ids
        assert itask.state.is_held is hold_expected

    assert get_task_ids(task_pool.tasks_to_hold) == expected_tasks_to_hold_ids

    logged_warnings = assert_expected_log(caplog, expected_warnings)
    assert n_warnings == len(logged_warnings)

    db_held_tasks = db_select(example_flow, True, 'tasks_to_hold')
    assert get_task_ids(db_held_tasks) == expected_tasks_to_hold_ids


async def test_release_held_tasks(
    example_flow: Scheduler, db_select: Callable
) -> None:
    """Test TaskPool.release_held_tasks().

    For a workflow with held active tasks 1/foo & 1/bar, and held future task
    3/asd.

    We skip testing the matching logic here because it would be slow using the
    function-scoped example_flow fixture, and it would repeat what is covered
    in test_hold_tasks().
    """
    # Setup
    task_pool = example_flow.pool
    expected_tasks_to_hold_ids = sorted(['1/foo', '1/bar', '3/asd'])
    task_pool.hold_tasks(expected_tasks_to_hold_ids)
    for itask in task_pool.get_all_tasks():
        hold_expected = itask.identity in expected_tasks_to_hold_ids
        assert itask.state.is_held is hold_expected
    assert get_task_ids(task_pool.tasks_to_hold) == expected_tasks_to_hold_ids
    db_tasks_to_hold = db_select(example_flow, True, 'tasks_to_hold')
    assert get_task_ids(db_tasks_to_hold) == expected_tasks_to_hold_ids

    # Test
    task_pool.release_held_tasks(['1/foo', '3/asd'])
    for itask in task_pool.get_all_tasks():
        assert itask.state.is_held is (itask.identity == '1/bar')

    expected_tasks_to_hold_ids = sorted(['1/bar'])
    assert get_task_ids(task_pool.tasks_to_hold) == expected_tasks_to_hold_ids

    db_tasks_to_hold = db_select(example_flow, True, 'tasks_to_hold')
    assert get_task_ids(db_tasks_to_hold) == expected_tasks_to_hold_ids


@pytest.mark.parametrize(
    'hold_after_point, expected_held_task_ids',
    [
        (0, ['1/foo', '1/bar', '2/foo', '2/bar', '2/pub', '3/foo', '3/bar',
             '4/foo', '4/bar', '5/foo', '5/bar']),
        (1, ['2/foo', '2/bar', '2/pub', '3/foo', '3/bar', '4/foo',
             '4/bar', '5/foo', '5/bar'])
    ]
)
async def test_hold_point(
    hold_after_point: int,
    expected_held_task_ids: List[str],
    example_flow: Scheduler, db_select: Callable
) -> None:
    """Test TaskPool.set_hold_point() and .release_hold_point()"""
    expected_held_task_ids = sorted(expected_held_task_ids)
    task_pool = example_flow.pool

    # Test hold
    task_pool.set_hold_point(IntegerPoint(hold_after_point))

    assert ('holdcp', str(hold_after_point)) in db_select(
        example_flow, True, 'workflow_params')

    for itask in task_pool.get_all_tasks():
        hold_expected = itask.identity in expected_held_task_ids
        assert itask.state.is_held is hold_expected

    assert get_task_ids(task_pool.tasks_to_hold) == expected_held_task_ids
    db_tasks_to_hold = db_select(example_flow, True, 'tasks_to_hold')
    assert get_task_ids(db_tasks_to_hold) == expected_held_task_ids

    # Test release
    task_pool.release_hold_point()

    assert db_select(example_flow, True, 'workflow_params', key='holdcp') == [
        ('holdcp', None)
    ]

    for itask in task_pool.get_all_tasks():
        assert itask.state.is_held is False

    assert task_pool.tasks_to_hold == set()
    assert db_select(example_flow, True, 'tasks_to_hold') == []


@pytest.mark.parametrize(
    'status,should_trigger',
    [
        (TASK_STATUS_WAITING, True),
        (TASK_STATUS_PREPARING, False),
        (TASK_STATUS_SUBMITTED, False),
        (TASK_STATUS_RUNNING, False),
        (TASK_STATUS_SUCCEEDED, True),
    ]
)
async def test_trigger_states(status, should_trigger, one, start):
    """It should only trigger tasks in compatible states."""

    async with start(one):
        task = one.pool.filter_task_proxies('1/a')[0][0]

        # reset task a to the provided state
        task.state.reset(status)

        # try triggering the task
        one.pool.force_trigger_tasks('1/a', [FLOW_ALL])

        # check whether the task triggered
        assert task.is_manual_submit == should_trigger


async def test_preparing_tasks_on_restart(one_conf, flow, scheduler, start):
    """Preparing tasks should be reset to waiting on restart.

    This forces preparation to be re-done on restart so that it uses the
    new configuration.

    See discussion on: https://github.com/cylc/cylc-flow/pull/4668

    """
    id_ = flow(one_conf)

    # start the workflow, reset a task to preparing
    one = scheduler(id_)
    async with start(one):
        task = one.pool.filter_task_proxies(['*'])[0][0]
        task.state.reset(TASK_STATUS_PREPARING)

    # when we restart the task should have been reset to waiting
    one = scheduler(id_)
    async with start(one):
        task = one.pool.filter_task_proxies(['*'])[0][0]
        assert task.state(TASK_STATUS_WAITING)
        task.state.reset(TASK_STATUS_SUCCEEDED)

    # whereas if we reset the task to succeeded the state is not reset
    one = scheduler(id_)
    async with start(one):
        task = one.pool.filter_task_proxies(['*'])[0][0]
        assert task.state(TASK_STATUS_SUCCEEDED)


async def test_reload_stopcp(
    flow: Callable, scheduler: Callable, start: Callable
):
    """Test that the task pool stopping point does not revert to the final
    cycle point on reload."""
    cfg = {
        'scheduler': {
            'allow implicit tasks': True,
            'cycle point format': 'CCYY',
        },
        'scheduling': {
            'initial cycle point': 2010,
            'stop after cycle point': 2020,
            'final cycle point': 2030,
            'graph': {
                'P1Y': 'anakin'
            }
        }
    }
    schd: Scheduler = scheduler(flow(cfg))
    async with start(schd):
        assert str(schd.pool.stop_point) == '2020'
        await schd.command_reload_workflow()
        assert str(schd.pool.stop_point) == '2020'


async def test_runahead_after_remove(
    example_flow: Scheduler
) -> None:
    """The runahead limit should be recomputed after tasks are removed.

    """
    task_pool = example_flow.pool
    assert int(task_pool.runahead_limit_point) == 4

    # No change after removing an intermediate cycle.
    task_pool.remove_tasks(['3/*'])
    assert int(task_pool.runahead_limit_point) == 4

    # Should update after removing the first point.
    task_pool.remove_tasks(['1/*'])
    assert int(task_pool.runahead_limit_point) == 5


async def test_load_db_bad_platform(
    flow: Callable, scheduler: Callable, start: Callable, one_conf: Callable
):
    """Test that loading an unavailable platform from the database doesn't
    cause calamitous failure."""
    schd: Scheduler = scheduler(flow(one_conf))

    async with start(schd):
        result = schd.pool.load_db_task_pool_for_restart(0, (
            '1', 'one', '{"1": 1}', "0", False, False, "failed",
            False, 1, '', 'culdee-fell-summit', '', '', '', '{}'
        ))
        assert result == 'culdee-fell-summit'


def list_tasks(schd):
    """Return a list of task pool tasks (incl hidden pool tasks).

    Returns a list in the format:
        [
            (cycle, task, state)
        ]

    """
    return sorted(
        (itask.tokens['cycle'], itask.tokens['task'], itask.state.status)
        for itask in schd.pool.get_all_tasks()
    )


@pytest.mark.parametrize(
    'graph_1, graph_2, '
    'expected_1, expected_2, expected_3, expected_4',
    [
        param(  # Restart after adding a prerequisite to task z
            '''a => z
               b => z''',
            '''a => z
               b => z
               c => z''',
            [
                ('1', 'a', 'running'),
                ('1', 'b', 'running'),
            ],
            [
                ('1', 'b', 'running'),
                ('1', 'z', 'waiting'),
            ],
            [
                ('1', 'b', 'running'),
                ('1', 'z', 'waiting'),
            ],
            [
                {('1', 'a', 'succeeded'): 'satisfied naturally'},
                {('1', 'b', 'succeeded'): False},
                {('1', 'c', 'succeeded'): False},
            ],
            id='added'
        ),
        param(  # Restart after removing a prerequisite from task z
            '''a => z
               b => z
               c => z''',
            '''a => z
               b => z''',
            [
                ('1', 'a', 'running'),
                ('1', 'b', 'running'),
                ('1', 'c', 'running'),
            ],
            [
                ('1', 'b', 'running'),
                ('1', 'c', 'running'),
                ('1', 'z', 'waiting'),
            ],
            [
                ('1', 'b', 'running'),
                ('1', 'c', 'running'),
                ('1', 'z', 'waiting'),
            ],
            [
                {('1', 'a', 'succeeded'): 'satisfied naturally'},
                {('1', 'b', 'succeeded'): False},
            ],
            id='removed'
        )
    ]
)
async def test_restart_prereqs(
    flow, scheduler, start,
    graph_1, graph_2,
    expected_1, expected_2, expected_3, expected_4
):
    """It should handle graph prerequisites change on restart.

    Prerequisite changes must be applied to tasks already in the pool.
    See https://github.com/cylc/cylc-flow/pull/5334

    """
    conf = {
        'scheduler': {'allow implicit tasks': 'True'},
        'scheduling': {
            'graph': {
                'R1': graph_1
            }
        }
    }
    id_ = flow(conf)
    schd = scheduler(id_, run_mode='simulation', paused_start=False)

    async with start(schd):
        # Release tasks 1/a and 1/b
        schd.pool.release_runahead_tasks()
        schd.release_queued_tasks()
        assert list_tasks(schd) == expected_1

        # Mark 1/a as succeeded and spawn 1/z
        schd.pool.get_all_tasks()[0].state_reset('succeeded')
        schd.pool.spawn_on_output(schd.pool.get_all_tasks()[0], 'succeeded')
        assert list_tasks(schd) == expected_2

        # Save our progress
        schd.workflow_db_mgr.put_task_pool(schd.pool)

    # Edit the workflow to add a new dependency on "z"
    conf['scheduling']['graph']['R1'] = graph_2
    id_ = flow(conf, id_=id_)

    # Restart it
    schd = scheduler(id_, run_mode='simulation', paused_start=False)
    async with start(schd):
        # Load jobs from db
        schd.workflow_db_mgr.pri_dao.select_jobs_for_restart(
            schd.data_store_mgr.insert_db_job
        )
        assert list_tasks(schd) == expected_3

        # To cover some code for loading prereqs from the DB at restart:
        schd.data_store_mgr.update_data_structure()

        # Check resulting dependencies of task z
        task_z = schd.pool.get_all_tasks()[0]
        assert sorted(
            (
                p.satisfied
                for p in task_z.state.prerequisites
            ),
            key=lambda d: tuple(d.keys())[0],
        ) == expected_4


@pytest.mark.parametrize(
    'graph_1, graph_2, '
    'expected_1, expected_2, expected_3, expected_4',
    [
        param(  # Reload after adding a prerequisite to task z
            '''a => z
               b => z''',
            '''a => z
               b => z
               c => z''',
            [
                ('1', 'a', 'running'),
                ('1', 'b', 'running'),
            ],
            [
                ('1', 'b', 'running'),
                ('1', 'z', 'waiting'),
            ],
            [
                ('1', 'b', 'running'),
                ('1', 'z', 'waiting'),
            ],
            [
                {('1', 'a', 'succeeded'): 'satisfied naturally'},
                {('1', 'b', 'succeeded'): False},
                {('1', 'c', 'succeeded'): False},
            ],
            id='added'
        ),
        param(  # Reload after removing a prerequisite from task z
            '''a => z
               b => z
               c => z''',
            '''a => z
               b => z''',
            [
                ('1', 'a', 'running'),
                ('1', 'b', 'running'),
                ('1', 'c', 'running'),
            ],
            [
                ('1', 'b', 'running'),
                ('1', 'c', 'running'),
                ('1', 'z', 'waiting'),
            ],
            [
                ('1', 'b', 'running'),
                ('1', 'c', 'running'),
                ('1', 'z', 'waiting'),
            ],
            [
                {('1', 'a', 'succeeded'): 'satisfied naturally'},
                {('1', 'b', 'succeeded'): False},
            ],
            id='removed'
        )
    ]
)
async def test_reload_prereqs(
    flow, scheduler, start,
    graph_1, graph_2,
    expected_1, expected_2, expected_3, expected_4
):
    """It should handle graph prerequisites change on reload.

    Prerequisite changes must be applied to tasks already in the pool.
    See https://github.com/cylc/cylc-flow/pull/5334

    """
    conf = {
        'scheduler': {'allow implicit tasks': 'True'},
        'scheduling': {
            'graph': {
                'R1': graph_1
            }
        }
    }
    id_ = flow(conf)
    schd = scheduler(id_, run_mode='simulation', paused_start=False)

    async with start(schd):
        # Release tasks 1/a and 1/b
        schd.pool.release_runahead_tasks()
        schd.release_queued_tasks()
        assert list_tasks(schd) == expected_1

        # Mark 1/a as succeeded and spawn 1/z
        schd.pool.get_all_tasks()[0].state_reset('succeeded')
        schd.pool.spawn_on_output(schd.pool.get_all_tasks()[0], 'succeeded')
        assert list_tasks(schd) == expected_2

        # Modify flow.cylc to add a new dependency on "z"
        conf['scheduling']['graph']['R1'] = graph_2
        flow(conf, id_=id_)

        # Reload the workflow config
        await schd.command_reload_workflow()
        assert list_tasks(schd) == expected_3

        # Check resulting dependencies of task z
        task_z = schd.pool.get_all_tasks()[0]
        assert sorted(
            (
                p.satisfied
                for p in task_z.state.prerequisites
            ),
            key=lambda d: tuple(d.keys())[0],
        ) == expected_4


async def _test_restart_prereqs_sat():
    # YIELD: the workflow has now started...
    schd = yield
    await schd.update_data_structure()

    # Release tasks 1/a and 1/b
    schd.pool.release_runahead_tasks()
    schd.release_queued_tasks()
    assert list_tasks(schd) == [
        ('1', 'a', 'running'),
        ('1', 'b', 'running')
    ]

    # Mark both as succeeded and spawn 1/c
    for itask in schd.pool.get_all_tasks():
        itask.state_reset('succeeded')
        schd.pool.spawn_on_output(itask, 'succeeded')
        schd.workflow_db_mgr.put_insert_task_outputs(itask)
        schd.pool.remove_if_complete(itask)
    schd.workflow_db_mgr.process_queued_ops()
    assert list_tasks(schd) == [
        ('1', 'c', 'waiting')
    ]

    # YIELD: the workflow has now restarted or reloaded with the new config...
    schd = yield
    await schd.update_data_structure()
    assert list_tasks(schd) == [
        ('1', 'c', 'waiting')
    ]

    # Check resulting dependencies of task z
    task_c = schd.pool.get_all_tasks()[0]
    assert sorted(
        (*key, satisfied)
        for prereq in task_c.state.prerequisites
        for key, satisfied in prereq.satisfied.items()
    ) == [
        ('1', 'a', 'succeeded', 'satisfied naturally'),
        ('1', 'b', 'succeeded', 'satisfied from database')
    ]

    # The prereqs in the data store should have been updated too
    # await schd.update_data_structure()
    tasks = (
        schd.data_store_mgr.data[schd.data_store_mgr.workflow_id][TASK_PROXIES]
    )
    task_c_prereqs = tasks[
        schd.data_store_mgr.id_.duplicate(cycle='1', task='c').id
    ].prerequisites
    assert sorted(
        (condition.task_proxy, condition.satisfied, condition.message)
        for prereq in task_c_prereqs
        for condition in prereq.conditions
    ) == [
        ('1/a', True, 'satisfied naturally'),
        ('1/b', True, 'satisfied from database'),
    ]

    # and we're done, yield back control and return
    yield


@pytest.mark.parametrize('do_restart', [True, False])
async def test_graph_change_prereq_satisfaction(
    flow, scheduler, start, do_restart
):
    """It should handle graph prerequisites change on reload/restart.

    If the graph is changed to add a dependency which has been previously
    satisfied, then Cylc should perform a DB check and mark the prerequsite
    as satisfied accordingly.

    See https://github.com/cylc/cylc-flow/pull/5334

    """
    conf = {
        'scheduler': {'allow implicit tasks': 'True'},
        'scheduling': {
            'graph': {
                'R1': '''
                    a => c
                    b
                '''
            }
        }
    }
    id_ = flow(conf)
    schd = scheduler(id_, run_mode='simulation', paused_start=False)

    test = _test_restart_prereqs_sat()
    await test.asend(None)

    if do_restart:
        async with start(schd):
            # start the workflow and run part 1 of the tests
            await test.asend(schd)

        # shutdown and change the workflow definiton
        conf['scheduling']['graph']['R1'] += '\nb => c'
        flow(conf, id_=id_)
        schd = scheduler(id_, run_mode='simulation', paused_start=False)

        async with start(schd):
            # restart the workflow and run part 2 of the tests
            await test.asend(schd)

    else:
        async with start(schd):
            await test.asend(schd)

            # Modify flow.cylc to add a new dependency on "b"
            conf['scheduling']['graph']['R1'] += '\nb => c'
            flow(conf, id_=id_)

            # Reload the workflow config
            await schd.command_reload_workflow()

            await test.asend(schd)


async def test_runahead_limit_for_sequence_before_start_cycle(
    flow,
    scheduler,
    start,
):
    """It should obey the runahead limit.

    Ensure the runahead limit is computed correctly for sequences before the start cycle

    See https://github.com/cylc/cylc-flow/issues/5603
    """
    id_ = flow({
        'scheduler': {'allow implicit tasks': 'True'},
        'scheduling': {
            'initial cycle point': '2000',
            'runahead limit': 'P2Y',
            'graph': {
                'R1/2000': 'a',
                'P1Y': 'b[-P1Y] => b',
            },
        }
    })
    schd = scheduler(id_, startcp='2005')
    async with start(schd):
        assert str(schd.pool.runahead_limit_point) == '20070101T0000Z'


def list_pool_from_db(schd):
    """Returns the task pool table as a sorted list."""
    db_task_pool = []
    schd.workflow_db_mgr.pri_dao.select_task_pool(
        lambda _, row: db_task_pool.append(row)
    )
    return sorted(db_task_pool)


async def test_db_update_on_removal(
    flow,
    scheduler,
    start,
):
    """It should updated the task_pool table when tasks complete.

    There was a bug where the task_pool table was only being updated when tasks
    in the pool were updated. This meant that if a task was removed the DB
    would not reflect this change and would hold a record of the task in the
    wrong state.

    This test ensures that the DB is updated when a task is removed from the
    pool.

    See: https://github.com/cylc/cylc-flow/issues/5598
    """
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'true',
        },
        'scheduling': {
            'graph': {
                'R1': 'a',
            },
        },
    })
    schd = scheduler(id_)
    async with start(schd):
        task_a = schd.pool.get_tasks()[0]

        # set the task to running
        task_a.state_reset('running')

        # update the db
        await schd.update_data_structure()
        schd.workflow_db_mgr.process_queued_ops()

        # the task should appear in the DB
        assert list_pool_from_db(schd) == [
            ['1', 'a', 'running', 0],
        ]

        # mark the task as succeeded and allow it to be removed from the pool
        task_a.state_reset('succeeded')
        schd.pool.remove_if_complete(task_a)

        # update the DB, note no new tasks have been added to the pool
        await schd.update_data_structure()
        schd.workflow_db_mgr.process_queued_ops()

        # the task should be gone from the DB
        assert list_pool_from_db(schd) == []


async def test_no_flow_tasks_dont_spawn(
    flow,
    scheduler,
    start,
):
    """Ensure no-flow tasks don't spawn downstreams.

    No-flow tasks (i.e `--flow=none`) are one-offs which are not attached to
    any "flow".

    See https://github.com/cylc/cylc-flow/issues/5613
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a => b => c'
            }
        },
        'scheduler': {
            'allow implicit tasks': 'true',
        },
    })

    schd = scheduler(id_)
    async with start(schd):
        # mark task 1/a as succeeded
        task_a = schd.pool.get_tasks()[0]
        task_a.state_reset(TASK_OUTPUT_SUCCEEDED)

        for flow_nums, force, pool in (
            # outputs yielded from a no-flow task should not spawn downstreams
            (set(), False, []),
            # forced spawning downstream of a no-flow task should spawn
            # downstreams with flow_nums={}
            (set(), True, [('1/b', set())]),
            # outputs yielded from a task with flow numbers should spawn
            # downstreams in the same flow
            ({1}, False, [('1/b', {1})]),
            # forced spawning should work in the same way
            ({1}, True, [('1/b', {1})]),
        ):
            # set the flow-nums on 1/a
            task_a.flow_nums = flow_nums

            # spawn on the succeeded output
            schd.pool.spawn_on_output(
                task_a,
                TASK_OUTPUT_SUCCEEDED,
                forced=force,
            )
            schd.pool.spawn_on_all_outputs(task_a)

            # ensure the pool is as expected
            assert [
                (itask.identity, itask.flow_nums)
                for pool in [
                    schd.pool.get_tasks(),
                    schd.pool.get_hidden_tasks(),
                ]
                for itask in pool
            ] == pool

async def test_task_proxy_remove_from_queues(
    flow, one_conf, scheduler, start,
):
    """TaskPool.remove deletes task proxies from queues."""
    # Set up a scheduler with a non-default queue:
    one_conf['scheduling'] = {
        'queues': {'queue_two': {'members': 'one, control'}},
        'graph': {'R1': 'two & one & hidden & control & hidden_control'},
    }
    schd = scheduler(flow(one_conf))
    async with start(schd):
        # Get a list of itasks:
        itasks = schd.pool.get_tasks()
        point = itasks[0].point

        for itask in itasks:
            id_ = itask.identity

            # Move some tasks to the hidden_pool to ensure that these are
            # removed too:
            if 'hidden' in itask.identity:
                schd.pool.hidden_pool.setdefault(point, {id_: itask})
                del schd.pool.main_pool[point][id_]

            # The meat of the test - remove itask from pool if it
            # doesn't have "control" in the name:
            if 'control' not in id_:
                schd.pool.remove(itask)

        # Look at the queues afterwards:
        queues_after = {
            name: [itask.identity for itask in queue.deque]
            for name, queue in schd.pool.task_queue_mgr.queues.items()}

        assert queues_after['default'] == ['1/hidden_control']
        assert queues_after['queue_two'] == ['1/control']

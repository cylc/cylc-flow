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

from cylc.flow import CYLC_LOG
from copy import deepcopy
import logging
import pytest
from pytest import param
from typing import AsyncGenerator, Callable, Iterable, List, Tuple, Union

from cylc.flow.cycling import PointBase
from cylc.flow.cycling.integer import IntegerPoint
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
    reg = mod_flow(EXAMPLE_FLOW_CFG)
    schd: Scheduler = mod_scheduler(reg, paused_start=True)
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
    reg = flow(EXAMPLE_FLOW_CFG)
    schd: Scheduler = scheduler(reg)
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

    assert db_select(example_flow, True, 'workflow_params', key='holdcp') == []

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
        schd.command_reload_workflow()
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


async def tests_restart_graph_change(flow, scheduler, start):
    """It should handle prerequisite changes on restart.

    If the graph has changed when a workflow is restarted those changes should
    be applied to tasks already in the pool.

    See https://github.com/cylc/cylc-flow/pull/5334

    """

    conf = {
        'scheduler': {'allow implicit tasks': 'True'},
        'scheduling': {
            'graph': {
                'R1': '''
                    a => z
                    b => z
                ''',
            }
        }
    }
    id_ = flow(conf)
    schd = scheduler(id_, run_mode='simulation', paused_start=False)

    async with start(schd):
        # release tasks 1/a and 1/b
        schd.pool.release_runahead_tasks()
        schd.release_queued_tasks()
        assert list_tasks(schd) == [
            ('1', 'a', 'running'),
            ('1', 'b', 'running'),
        ]

        # mark 1/a as succeeded and spawn 1/z
        schd.pool.get_all_tasks()[0].state_reset('succeeded')
        schd.pool.spawn_on_output(schd.pool.get_all_tasks()[0], 'succeeded')
        assert list_tasks(schd) == [
            ('1', 'b', 'running'),
            ('1', 'z', 'waiting'),
        ]

        # save our progress
        schd.workflow_db_mgr.put_task_pool(schd.pool)

    # edit the workflow to add a new dependency on "z"
    conf['scheduling']['graph']['R1'] += '\n c => z'
    id_ = flow(conf, id_=id_)

    # and restart it
    schd = scheduler(id_, run_mode='simulation', paused_start=False)
    async with start(schd):
        # load jobs from db
        schd.pool.reload_taskdefs()
        schd.workflow_db_mgr.pri_dao.select_jobs_for_restart(
            schd.data_store_mgr.insert_db_job
        )
        assert list_tasks(schd) == [
            ('1', 'b', 'running'),
            ('1', 'z', 'waiting'),
        ]

        # ensure the new dependency 1/c has been added to 1/z
        # and is *not* satisfied
        task_z = schd.pool.get_all_tasks()[0]
        assert sorted(
            (
                p.satisfied
                for p in task_z.state.prerequisites
            ),
            key=lambda d: tuple(d.keys())[0],
        ) == [
            {('1', 'a', 'succeeded'): 'satisfied naturally'},
            {('1', 'b', 'succeeded'): False},
            {('1', 'c', 'succeeded'): False},

        ]

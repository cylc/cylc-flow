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

from json import loads
import logging
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Callable,
    Iterable,
    List,
    Tuple,
    Union,
)

import pytest
from pytest import param

from cylc.flow import (
    CYLC_LOG,
    commands,
)
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.data_messages_pb2 import PbPrerequisite
from cylc.flow.data_store_mgr import TASK_PROXIES
from cylc.flow.flow_mgr import (
    FLOW_ALL,
    FLOW_NONE,
)
from cylc.flow.task_events_mgr import TaskEventsManager
from cylc.flow.task_outputs import (
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_SUCCEEDED,
)
from cylc.flow.task_state import (
    TASK_STATUS_EXPIRED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
)


if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase
    from cylc.flow.scheduler import Scheduler

# NOTE: foo and bar have no parents so at start-up (even with the workflow
# paused) they get spawned out to the runahead limit. 2/pub spawns
# immediately too, because we spawn autospawn absolute-triggered tasks as
# well as parentless tasks. 3/asd does not spawn at start, however.
EXAMPLE_FLOW_CFG = {
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


EXAMPLE_FLOW_2_CFG = {
    'scheduler': {
        'UTC mode': True
    },
    'scheduling': {
        'initial cycle point': '2001',
        'runahead limit': 'P3Y',
        'graph': {
            'P1Y': 'foo',
            'R/2025/P1Y': 'foo => bar',
        }
    },
}


def get_task_ids(
    name_point_list: Iterable[Tuple[str, Union['PointBase', str, int]]]
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
) -> AsyncGenerator['Scheduler', None]:
    """Return a scheduler for interrogating its task pool.

    This is module-scoped so faster than example_flow, but should only be used
    where the test does not mutate the state of the scheduler or task pool.
    """
    id_ = mod_flow(EXAMPLE_FLOW_CFG)
    schd: 'Scheduler' = mod_scheduler(id_, paused_start=True)
    async with mod_run(schd, level=logging.DEBUG):
        yield schd


@pytest.fixture
async def example_flow(
    flow: Callable,
    scheduler: Callable,
    start,
    caplog: pytest.LogCaptureFixture,
) -> AsyncGenerator['Scheduler', None]:
    """Return a scheduler for interrogating its task pool.

    This is function-scoped so slower than mod_example_flow; only use this
    when the test mutates the scheduler or task pool.
    """
    # The run(schd) fixture doesn't work for modifying the DB, so have to
    # set up caplog and do schd.install()/.initialise()/.configure() instead
    caplog.set_level(logging.INFO, CYLC_LOG)
    id_ = flow(EXAMPLE_FLOW_CFG)
    schd: 'Scheduler' = scheduler(id_)
    async with start(schd, level=logging.DEBUG):
        yield schd


@pytest.fixture(scope='module')
async def mod_example_flow_2(
    mod_flow: Callable, mod_scheduler: Callable, mod_run: Callable
) -> AsyncGenerator['Scheduler', None]:
    """Return a scheduler for interrogating its task pool.

    This is module-scoped so faster than example_flow, but should only be used
    where the test does not mutate the state of the scheduler or task pool.
    """
    id_ = mod_flow(EXAMPLE_FLOW_2_CFG)
    schd: 'Scheduler' = mod_scheduler(id_, paused_start=True)
    async with mod_run(schd):
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
    mod_example_flow: 'Scheduler',
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
    mod_example_flow: 'Scheduler',
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
            id="Active & inactive tasks"
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
            id=(
                "Specifying task state works for active tasks,"
                " not inactive tasks"
            )
        )
    ]
)
async def test_hold_tasks(
    items: List[str],
    expected_tasks_to_hold_ids: List[str],
    expected_warnings: List[str],
    example_flow: 'Scheduler', caplog: pytest.LogCaptureFixture,
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

    for itask in task_pool.get_tasks():
        hold_expected = itask.identity in expected_tasks_to_hold_ids
        assert itask.state.is_held is hold_expected

    assert get_task_ids(task_pool.tasks_to_hold) == expected_tasks_to_hold_ids

    logged_warnings = assert_expected_log(caplog, expected_warnings)
    assert n_warnings == len(logged_warnings)

    db_held_tasks = db_select(example_flow, True, 'tasks_to_hold')
    assert get_task_ids(db_held_tasks) == expected_tasks_to_hold_ids


async def test_release_held_tasks(
    example_flow: 'Scheduler', db_select: Callable
) -> None:
    """Test TaskPool.release_held_tasks().

    For a workflow with held active tasks 1/foo & 1/bar, and held inactive task
    3/asd.

    We skip testing the matching logic here because it would be slow using the
    function-scoped example_flow fixture, and it would repeat what is covered
    in test_hold_tasks().
    """
    # Setup
    task_pool = example_flow.pool
    expected_tasks_to_hold_ids = sorted(['1/foo', '1/bar', '3/asd'])
    task_pool.hold_tasks(expected_tasks_to_hold_ids)
    for itask in task_pool.get_tasks():
        hold_expected = itask.identity in expected_tasks_to_hold_ids
        assert itask.state.is_held is hold_expected
    assert get_task_ids(task_pool.tasks_to_hold) == expected_tasks_to_hold_ids
    db_tasks_to_hold = db_select(example_flow, True, 'tasks_to_hold')
    assert get_task_ids(db_tasks_to_hold) == expected_tasks_to_hold_ids

    # Test
    task_pool.release_held_tasks(['1/foo', '3/asd'])
    for itask in task_pool.get_tasks():
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
    example_flow: 'Scheduler', db_select: Callable
) -> None:
    """Test TaskPool.set_hold_point() and .release_hold_point()"""
    expected_held_task_ids = sorted(expected_held_task_ids)
    task_pool = example_flow.pool

    # Test hold
    task_pool.set_hold_point(IntegerPoint(hold_after_point))

    assert ('holdcp', str(hold_after_point)) in db_select(
        example_flow, True, 'workflow_params')

    for itask in task_pool.get_tasks():
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

    for itask in task_pool.get_tasks():
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
async def test_trigger_states(
    status: str, should_trigger: bool, one: 'Scheduler', start: Callable
):
    """It should only trigger tasks in compatible states."""

    async with start(one):
        task = one.pool.filter_task_proxies(['1/one'])[0][0]

        # reset task a to the provided state
        task.state.reset(status)

        # try triggering the task
        one.pool.force_trigger_tasks(['1/one'], [FLOW_ALL])

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
    schd: 'Scheduler' = scheduler(flow(cfg))
    async with start(schd):
        assert str(schd.pool.stop_point) == '2020'
        await commands.run_cmd(commands.reload_workflow(schd))
        assert str(schd.pool.stop_point) == '2020'


async def test_runahead_after_remove(
    example_flow: 'Scheduler'
) -> None:
    """The runahead limit should be recomputed after tasks are removed.

    """
    task_pool = example_flow.pool
    assert int(task_pool.runahead_limit_point) == 4

    # No change after removing an intermediate cycle.
    example_flow.remove_tasks(['3/*'])
    assert int(task_pool.runahead_limit_point) == 4

    # Should update after removing the first point.
    example_flow.remove_tasks(['1/*'])
    assert int(task_pool.runahead_limit_point) == 5


async def test_load_db_bad_platform(
    flow: Callable, scheduler: Callable, start: Callable, one_conf: Callable
):
    """Test that loading an unavailable platform from the database doesn't
    cause calamitous failure."""
    schd: 'Scheduler' = scheduler(flow(one_conf))

    async with start(schd):
        result = schd.pool.load_db_task_pool_for_restart(0, (
            '1', 'one', '{"1": 1}', "0", False, False, "failed",
            False, 1, '', 'culdee-fell-summit', '', '', '', '{}'
        ))
        assert result == 'culdee-fell-summit'


def list_tasks(schd):
    """Return a sorted list of task pool tasks.

    Returns a list in the format:
        [
            (cycle, task, state)
        ]

    """
    return sorted(
        (itask.tokens['cycle'], itask.tokens['task'], itask.state.status)
        for itask in schd.pool.get_tasks()
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
    schd: Scheduler = scheduler(id_, paused_start=False)

    async with start(schd):
        # Release tasks 1/a and 1/b
        schd.pool.release_runahead_tasks()
        schd.release_tasks_to_run()
        assert list_tasks(schd) == expected_1

        # Mark 1/a as succeeded and spawn 1/z
        task_a = schd.pool.get_tasks()[0]
        schd.pool.task_events_mgr.process_message(task_a, 1, 'succeeded')
        assert list_tasks(schd) == expected_2

        # Save our progress
        schd.workflow_db_mgr.put_task_pool(schd.pool)

    # Edit the workflow to add a new dependency on "z"
    conf['scheduling']['graph']['R1'] = graph_2
    id_ = flow(conf, workflow_id=id_)

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
        task_z = [
            t for t in schd.pool.get_tasks() if t.tdef.name == "z"
        ][0]
        assert sorted(
            (
                p._satisfied
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
    schd: Scheduler = scheduler(id_, paused_start=False)

    async with start(schd):
        # Release tasks 1/a and 1/b
        schd.pool.release_runahead_tasks()
        schd.release_tasks_to_run()
        assert list_tasks(schd) == expected_1

        # Mark 1/a as succeeded and spawn 1/z
        task_a = schd.pool.get_tasks()[0]
        schd.pool.task_events_mgr.process_message(task_a, 1, 'succeeded')
        assert list_tasks(schd) == expected_2

        # Modify flow.cylc to add a new dependency on "z"
        conf['scheduling']['graph']['R1'] = graph_2
        flow(conf, workflow_id=id_)

        # Reload the workflow config
        await commands.run_cmd(commands.reload_workflow(schd))
        assert list_tasks(schd) == expected_3

        # Check resulting dependencies of task z
        task_z = [
            t for t in schd.pool.get_tasks() if t.tdef.name == "z"
        ][0]
        assert sorted(
            (
                p._satisfied
                for p in task_z.state.prerequisites
            ),
            key=lambda d: tuple(d.keys())[0],
        ) == expected_4


async def _test_restart_prereqs_sat():
    schd: Scheduler
    # YIELD: the workflow has now started...
    schd = yield
    await schd.update_data_structure()

    # Release tasks 1/a and 1/b
    schd.pool.release_runahead_tasks()
    schd.release_tasks_to_run()
    assert list_tasks(schd) == [
        ('1', 'a', 'running'),
        ('1', 'b', 'running')
    ]

    # Mark both as succeeded and spawn 1/c
    for itask in schd.pool.get_tasks():
        schd.pool.task_events_mgr.process_message(itask, 1, 'succeeded')
        schd.workflow_db_mgr.put_update_task_outputs(itask)
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
    task_c = schd.pool.get_tasks()[0]
    assert sorted(
        (*key, satisfied)
        for prereq in task_c.state.prerequisites
        for key, satisfied in prereq.items()
    ) == [
        ('1', 'a', 'succeeded', 'satisfied naturally'),
        ('1', 'b', 'succeeded', 'satisfied from database')
    ]

    # The prereqs in the data store should have been updated too
    # await schd.update_data_structure()
    tasks = (
        schd.data_store_mgr.data[schd.data_store_mgr.workflow_id][TASK_PROXIES]
    )
    task_c_prereqs: List[PbPrerequisite] = tasks[
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
        flow(conf, workflow_id=id_)
        schd = scheduler(id_, run_mode='simulation', paused_start=False)

        async with start(schd):
            # restart the workflow and run part 2 of the tests
            await test.asend(schd)

    else:
        async with start(schd):
            await test.asend(schd)

            # Modify flow.cylc to add a new dependency on "b"
            conf['scheduling']['graph']['R1'] += '\nb => c'
            flow(conf, workflow_id=id_)

            # Reload the workflow config
            await commands.run_cmd(commands.reload_workflow(schd))

            await test.asend(schd)


async def test_runahead_limit_for_sequence_before_start_cycle(
    flow,
    scheduler,
    start,
):
    """It should obey the runahead limit.

    Ensure the runahead limit is computed correctly for sequences before the
    start cycle

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
        schd.pool.task_events_mgr.process_message(task_a, 1, 'started')

        # update the db
        await schd.update_data_structure()
        schd.workflow_db_mgr.process_queued_ops()

        # the task should appear in the DB
        assert list_pool_from_db(schd) == [
            ['1', 'a', 'running', 0],
        ]

        # mark the task as succeeded and allow it to be removed from the pool
        schd.pool.task_events_mgr.process_message(task_a, 1, 'succeeded')
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

    No-flow tasks (i.e `--flow=none`) are not attached to any "flow".

    See https://github.com/cylc/cylc-flow/issues/5613
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a => b => c'
            }
        },
    })

    schd: Scheduler = scheduler(id_)
    async with start(schd):
        task_a = schd.pool.get_tasks()[0]

        # set as no-flow:
        task_a.flow_nums = set()

        # Set as completed: should not spawn children.
        schd.pool.set_prereqs_and_outputs(
            [task_a.identity], [], [], [FLOW_NONE]
        )
        assert not schd.pool.get_tasks()

        for flow_nums, expected_pool in (
            # outputs yielded from a no-flow task should not spawn downstreams
            (set(), []),
            # outputs yielded from a task with flow numbers should spawn
            # downstreams in the same flow
            ({1}, [('1/b', {1})]),
        ):
            # set the flow-nums on 1/a
            task_a.flow_nums = flow_nums

            # spawn on the succeeded output
            schd.pool.spawn_on_output(task_a, TASK_OUTPUT_SUCCEEDED)

            schd.pool.spawn_on_all_outputs(task_a)

            # ensure the pool is as expected
            assert [
                (itask.identity, itask.flow_nums)
                for itask in schd.pool.get_tasks()
            ] == expected_pool


async def test_task_proxy_remove_from_queues(
    flow, one_conf, scheduler, start,
):
    """TaskPool.remove should delete task proxies from queues.

    See https://github.com/cylc/cylc-flow/pull/5573
    """
    # Set up a scheduler with a non-default queue:
    one_conf['scheduling'] = {
        'queues': {'queue_two': {'members': 'one, control'}},
        'graph': {'R1': 'two & one & control'},
    }
    schd = scheduler(flow(one_conf))
    async with start(schd):
        # Get a list of itasks:
        itasks = schd.pool.get_tasks()

        for itask in itasks:
            id_ = itask.identity

            # The meat of the test - remove itask from pool if it
            # doesn't have "control" in the name:
            if 'control' not in id_:
                schd.pool.remove(itask)

        # Look at the queues afterwards:
        queues_after = {
            name: [itask.identity for itask in queue.deque]
            for name, queue in schd.pool.task_queue_mgr.queues.items()}

        assert queues_after['queue_two'] == ['1/control']


async def test_runahead_offset_start(
    mod_example_flow_2: 'Scheduler'
) -> None:
    """Late-start recurrences should not break the runahead limit at start-up.

    See GitHub #5708
    """
    task_pool = mod_example_flow_2.pool
    assert task_pool.runahead_limit_point == ISO8601Point('2004')


async def test_detect_incomplete_tasks(
    flow,
    scheduler,
    start,
    log_filter,
):
    """Finished but incomplete tasks should be retained as incomplete."""
    incomplete_final_task_states = {
        # final task states that would leave a task with
        # completion=succeeded incomplete
        TASK_STATUS_FAILED: TaskEventsManager.EVENT_FAILED,
        TASK_STATUS_EXPIRED: TaskEventsManager.EVENT_EXPIRED,
        TASK_STATUS_SUBMIT_FAILED: TaskEventsManager.EVENT_SUBMIT_FAILED
    }
    id_ = flow({
        'scheduling': {
            'graph': {
                # a workflow with one task for each of the final task states
                'R1': '\n'.join(incomplete_final_task_states.keys())
            }
        }
    })
    schd = scheduler(id_)
    async with start(schd, level=logging.DEBUG):
        itasks = schd.pool.get_tasks()
        for itask in itasks:
            itask.state_reset(is_queued=False)
            # spawn the output corresponding to the task
            schd.pool.task_events_mgr.process_message(
                itask, 1,
                incomplete_final_task_states[itask.tdef.name]
            )
            # ensure that it is correctly identified as incomplete
            assert not itask.state.outputs.is_complete()
            assert log_filter(
                contains=(
                    f"[{itask}] did not complete the required outputs:"
                ),
            )
            # the task should not have been removed
            assert itask in schd.pool.get_tasks()


async def test_future_trigger_final_point(
    flow,
    scheduler,
    start,
    log_filter,
):
    """Check spawning of future-triggered tasks: foo[+P1] => bar.

    Don't spawn if a prerequisite reaches beyond the final cycle point.

    """
    id_ = flow(
        {
            'scheduling': {
                'cycling mode': 'integer',
                'initial cycle point': 1,
                'final cycle point': 1,
                'graph': {
                    'P1': "foo\n foo[+P1] & bar => baz"
                }
            }
        }
    )
    schd = scheduler(id_)
    async with start(schd):
        for itask in schd.pool.get_tasks():
            schd.pool.spawn_on_output(itask, "succeeded")
        assert log_filter(
            regex=(
                ".*1/baz.*not spawned: a prerequisite is beyond"
                r" the workflow stop point \(1\)"
            )
        )


async def test_set_failed_complete(
    flow,
    scheduler,
    start,
    one_conf,
    log_filter,
    db_select: Callable
):
    """Test manual completion of an incomplete failed task."""
    id_ = flow(one_conf)
    schd: Scheduler = scheduler(id_)
    async with start(schd, level=logging.DEBUG):
        one = schd.pool.get_tasks()[0]
        one.state_reset(is_queued=False)

        schd.pool.task_events_mgr.process_message(one, 1, "failed")
        assert log_filter(
            regex="1/one.* setting implied output: submitted")
        assert log_filter(
            regex="1/one.* setting implied output: started")
        assert log_filter(
            regex="failed.* did not complete the required outputs")

        # Set failed task complete via default "set" args.
        schd.pool.set_prereqs_and_outputs([one.identity], [], [], ['all'])

        assert log_filter(
            contains=f'[{one}] removed from active task pool: completed')

        db_outputs = db_select(
            schd, True, 'task_outputs', 'outputs',
            **{'name': 'one'}
        )
        assert (
            sorted(loads((db_outputs[0])[0])) == [
                "failed", "started", "submitted", "succeeded"
            ]
        )


async def test_set_prereqs_and_xtrigs(
    flow,
    scheduler,
    start,
    log_filter,
):
    """Check manual setting of prerequisites.

    """
    id_ = flow(
        {
            'scheduling': {
                'initial cycle point': '2040',
                'xtriggers': {
                    'x': 'xrandom(0)'
                },
                'graph': {
                    'R1': """
                        foo & bar & baz => qux",
                        @x => bar
                    """
                }
            },
            'runtime': {
                'foo': {
                    'outputs': {
                        'a': 'drugs and money',
                    }
                }
            }
        }
    )
    schd: Scheduler = scheduler(id_)

    async with start(schd):

        # it should start up with foo, bar, baz
        assert schd.pool.get_task_ids() == {
            "20400101T0000Z/bar",
            "20400101T0000Z/baz",
            "20400101T0000Z/foo",
        }

        # try to set an invalid prereq of qux
        schd.pool.set_prereqs_and_outputs(
            ["20400101T0000Z/qux"], [],
            ["20400101T0000Z/foo:a", "xtrigger/x"], ['all']
        )
        assert log_filter(
            contains=(
                '20400101T0000Z/qux does not depend on "20400101T0000Z/foo:a"'
            )
        )
        assert log_filter(
            contains=(
                '20400101T0000Z/qux does not depend on xtrigger "x"'
            )
        )

        # it should not add 20400101T0000Z/qux to the pool
        assert schd.pool.get_task_ids() == {
            "20400101T0000Z/bar",
            "20400101T0000Z/baz",
            "20400101T0000Z/foo",
        }

        # set an xtrigger (see also test_xtrigger_mgr, and test_data_store_mgr)
        bar = schd.pool._get_task_by_id('20400101T0000Z/bar')
        assert bar.state.prerequisites_all_satisfied()
        assert not bar.state.xtriggers_all_satisfied()
        schd.pool.set_prereqs_and_outputs(
            ["20400101T0000Z/bar"],
            [],
            ["xtrigger/x:satisfied"],
            ['all']
        )
        assert bar.state.xtriggers_all_satisfied()
        assert log_filter(
            contains=(
                'xtrigger prerequisite satisfied (forced): x = xrandom(0)'))

        # set xtrigger in the wrong task
        schd.pool.set_prereqs_and_outputs(
            ["20400101T0000Z/baz"],
            [],
            ["xtrigger/x:succeeded"],
            ['all']
        )
        assert log_filter(
            contains='20400101T0000Z/baz does not depend on xtrigger "x"')

        # set one prereq of inactive task 20400101T0000Z/qux
        schd.pool.set_prereqs_and_outputs(
            ["20400101T0000Z/qux"],
            [],
            ["20400101T0000Z/foo:succeeded"],
            ['all'])

        # it should add 20400101T0000Z/qux to the pool
        assert schd.pool.get_task_ids() == {
            "20400101T0000Z/bar",
            "20400101T0000Z/baz",
            "20400101T0000Z/foo",
            "20400101T0000Z/qux",
        }

        # get the 20400101T0000Z/qux task proxy
        qux = schd.pool.get_task(ISO8601Point("20400101T0000Z"), "qux")
        assert not qux.state.prerequisites_all_satisfied()

        # set its other prereqs (test implicit "succeeded" and "succeed")
        # and truncated cycle point
        schd.pool.set_prereqs_and_outputs(
            ["2040/qux"], [], ["2040/bar", "2040/baz:succeed"], ['all'])

        assert log_filter(
            contains=('prerequisite satisfied (forced): 20400101T0000Z/bar'))
        assert log_filter(
            contains=('prerequisite satisfied (forced): 20400101T0000Z/baz'))

        # it should now be fully satisfied
        assert qux.state.prerequisites_all_satisfied()

        # set one again
        schd.pool.set_prereqs_and_outputs(
            ["2040/qux"], [], ["2040/bar"], ['all'])

        assert log_filter(
            contains=('prerequisite already satisfied: 20400101T0000Z/bar'))


async def test_set_bad_prereqs(
    flow,
    scheduler,
    start,
    log_filter,
):
    """Check manual setting of prerequisites.

    """
    id_ = flow({
        'scheduler': {
            'cycle point format': '%Y'},
        'scheduling': {
            'initial cycle point': '2040',
            'graph': {'R1': "foo => bar"}},
    })
    schd: Scheduler = scheduler(id_)

    def set_prereqs(prereqs):
        """Shorthand so only varible under test given as arg"""
        schd.pool.set_prereqs_and_outputs(
            ["2040/bar"], [], prereqs, ['all'])

    async with start(schd):
        # Invalid: task name wildcard:
        set_prereqs(["2040/*"])
        assert log_filter(contains='Invalid prerequisite task name')

        # Invalid: cycle point wildcard.
        set_prereqs(["*/foo"])
        assert log_filter(contains='Invalid prerequisite cycle point')


async def test_set_outputs_live(
    flow,
    scheduler,
    start,
    log_filter,
):
    """Check manual set outputs in an active (spawned) task.

    """
    id_ = flow(
        {
            'scheduling': {
                'graph': {
                    'R1': """
                        foo:x => bar
                        foo => baz
                        foo:y
                    """
                }
            },
            'runtime': {
                'foo': {
                    'outputs': {
                        'x': 'xylophone',
                        'y': 'yacht'
                    }
                }
            }
        }
    )
    schd: Scheduler = scheduler(id_)

    async with start(schd):

        # it should start up with just 1/foo
        assert schd.pool.get_task_ids() == {"1/foo"}

        # fake failed
        foo = schd.pool.get_task(IntegerPoint("1"), "foo")
        foo.state_reset(is_queued=False)
        schd.pool.task_events_mgr.process_message(foo, 1, 'failed')

        # set foo:x: it should spawn bar but not baz
        schd.pool.set_prereqs_and_outputs(["1/foo"], ["x"], [], ['all'])
        assert schd.pool.get_task_ids() == {"1/bar", "1/foo"}
        # Foo should have been removed from the queue:
        assert '1/foo' not in [
            i.identity for i
            in schd.pool.task_queue_mgr.queues['default'].deque
        ]
        # set foo:succeed: it should spawn baz but foo remains incomplete.
        schd.pool.set_prereqs_and_outputs(
            ["1/foo"], ["succeeded"], [], ['all'])
        assert schd.pool.get_task_ids() == {"1/bar", "1/baz", "1/foo"}

        # it should complete implied outputs (submitted, started) too
        assert log_filter(contains="setting implied output: submitted")
        assert log_filter(contains="setting implied output: started")

        # set foo (default: all required outputs) to complete y.
        schd.pool.set_prereqs_and_outputs(["1/foo"], [], [], ['all'])
        assert log_filter(contains="output 1/foo:succeeded completed")
        assert schd.pool.get_task_ids() == {"1/bar", "1/baz"}


async def test_set_outputs_live2(
    flow,
    scheduler,
    start,
    log_filter,
):
    """Assert that optional outputs are satisfied before completion
    outputs to prevent incomplete task warnings.
    """
    id_ = flow(
        {
            'scheduling': {'graph': {
                'R1': """
                    foo:a => apple
                    foo:b => boat
                """}},
            'runtime': {'foo': {'outputs': {
                'a': 'xylophone',
                'b': 'yacht'}}}
        }
    )
    schd: Scheduler = scheduler(id_)

    async with start(schd):
        schd.pool.set_prereqs_and_outputs(["1/foo"], [], [], ['all'])
        assert not log_filter(
            contains="did not complete required outputs: ['a', 'b']"
        )


async def test_set_outputs_future(
    flow,
    scheduler,
    start,
    log_filter,
):
    """Check manual setting of inactive task outputs.

    """
    id_ = flow(
        {
            'scheduling': {
                'graph': {
                    'R1': "a:x & a:y => b => c"
                }
            },
            'runtime': {
                'a': {
                    'outputs': {
                        'x': 'xylophone',
                        'y': 'yacht'
                    }
                }
            }
        }
    )
    schd: Scheduler = scheduler(id_)

    async with start(schd):

        # it should start up with just 1/a
        assert schd.pool.get_task_ids() == {"1/a"}

        # setting inactive task b succeeded should spawn c but not b
        schd.pool.set_prereqs_and_outputs(
            ["1/b"], ["succeeded"], [], ['all'])
        assert schd.pool.get_task_ids() == {"1/a", "1/c"}

        schd.pool.set_prereqs_and_outputs(
            items=["1/a"],
            outputs=["x", "y", "cheese"],
            prereqs=[],
            flow=['all']
        )
        assert log_filter(contains="Output 1/a:cheese not found")
        assert log_filter(contains="completed output x")
        assert log_filter(contains="completed output y")


async def test_set_outputs_from_skip_settings(
    flow,
    scheduler,
    start,
    log_filter,
    validate
):
    """Check working of ``cylc set --out=skip``:

    1. --out=skip can be used to set all required outputs.
    2. --out=skip,other_output can be used to set other outputs.

    """
    id_ = flow(
        {
            'scheduling': {
                'cycling mode': 'integer',
                'initial cycle point': 1,
                'final cycle point': 2,
                'graph': {
                    'P1': """
                        a => after_asucceeded
                        a:x => after_ax
                        a:y? => after_ay
                    """
                }
            },
            'runtime': {
                'a': {
                    'outputs': {
                        'x': 'xebec',
                        'y': 'yacht'
                    },
                    'skip': {'outputs': 'x'}
                }
            }
        }
    )
    validate(id_)
    schd: Scheduler = scheduler(id_)

    async with start(schd):
        # it should start up with just tasks a:
        assert schd.pool.get_task_ids() == {'1/a', '2/a'}

        # setting 1/a output to skip should set output x, but not
        # y (because y is optional).
        schd.pool.set_prereqs_and_outputs(
            ['1/a'], ['skip'], [], ['all'])
        assert schd.pool.get_task_ids() == {
            '1/after_asucceeded',
            '1/after_ax',
            '2/a',
        }

        # Check that the presence of "skip" in outputs doesn't
        # trigger a warning:
        assert not log_filter(level=30)

        # You should be able to set skip as part of a list of outputs:
        schd.pool.set_prereqs_and_outputs(
            ['2/a'], ['skip', 'y'], [], ['all'])
        assert schd.pool.get_task_ids() == {
            '1/after_asucceeded',
            '1/after_ax',
            '2/after_asucceeded',
            '2/after_ax',
            '2/after_ay',
        }


async def test_prereq_satisfaction(
    flow,
    scheduler,
    start,
    log_filter,
):
    """Check manual setting of task prerequisites.

    """
    id_ = flow(
        {
            'scheduling': {
                'graph': {
                    'R1': "a:x & a:y => b"
                }
            },
            'runtime': {
                'a': {
                    'outputs': {
                        'x': 'xylophone',
                        'y': 'yacht'
                    }
                }
            }
        }
    )
    schd: Scheduler = scheduler(id_)
    async with start(schd):
        # it should start up with just 1/a
        assert schd.pool.get_task_ids() == {"1/a"}
        # spawn b
        schd.pool.set_prereqs_and_outputs(["1/a"], ["x"], [], ['all'])
        assert schd.pool.get_task_ids() == {"1/a", "1/b"}

        b = schd.pool.get_task(IntegerPoint("1"), "b")

        assert not b.prereqs_are_satisfied()

        # set valid and invalid prerequisites, by label and message.
        schd.pool.set_prereqs_and_outputs(
            prereqs=["1/a:xylophone", "1/a:y", "1/a:w", "1/a:z"],
            items=["1/b"], outputs=[], flow=['all']
        )
        assert log_filter(contains="1/a:z not found")
        assert log_filter(contains="1/a:w not found")
        # FIXME: testing that something is *not* logged is extremely fragile:
        assert not log_filter(regex='.*does not depend on.*')

        assert b.prereqs_are_satisfied()


@pytest.mark.parametrize('compat_mode', ['compat-mode', 'normal-mode'])
@pytest.mark.parametrize('cycling_mode', ['integer', 'datetime'])
@pytest.mark.parametrize('runahead_format', ['P3Y', 'P3'])
async def test_compute_runahead(
    cycling_mode,
    compat_mode,
    runahead_format,
    flow,
    scheduler,
    start,
    monkeypatch,
):
    """Test the calculation of the runahead limit.

    This test ensures that:
    * Runahead tasks are excluded from computations
      see https://github.com/cylc/cylc-flow/issues/5825
    * Tasks are initiated with the correct is_runahead status on startup.
    * Behaviour in compat/regular modes is same unless failed tasks are present
    * Behaviour is the same for integer/datetime cycling modes.

    """
    if cycling_mode == 'integer':

        config = {
            'scheduler': {
                'allow implicit tasks': 'True',
            },
            'scheduling': {
                'initial cycle point': '1',
                'cycling mode': 'integer',
                'runahead limit': 'P3',
                'graph': {
                    'P1': 'a'
                },
            }
        }
        point = lambda point: IntegerPoint(str(int(point)))
    else:
        config = {
            'scheduler': {
                'allow implicit tasks': 'True',
                'cycle point format': 'CCYY',
            },
            'scheduling': {
                'initial cycle point': '0001',
                'runahead limit': runahead_format,
                'graph': {
                    'P1Y': 'a'
                },
            }
        }
        point = ISO8601Point

    monkeypatch.setattr(
        'cylc.flow.flags.cylc7_back_compat',
        compat_mode == 'compat-mode',
    )

    id_ = flow(config)
    schd = scheduler(id_)
    async with start(schd):
        schd.pool.compute_runahead(force=True)
        assert int(str(schd.pool.runahead_limit_point)) == 4

        # ensure task states are initiated with is_runahead status
        assert schd.pool.get_task(point('0001'), 'a').state(is_runahead=False)
        assert schd.pool.get_task(point('0005'), 'a').state(is_runahead=True)

        # mark the first three cycles as running
        for cycle in range(1, 4):
            schd.pool.get_task(point(f'{cycle:04}'), 'a').state.reset(
                TASK_STATUS_RUNNING
            )

        schd.pool.compute_runahead(force=True)
        assert int(str(schd.pool.runahead_limit_point)) == 4  # no change

        # In Cylc 8 all incomplete tasks hold back runahead.

        # In Cylc 7, submit-failed tasks hold back runahead..
        schd.pool.get_task(point('0001'), 'a').state.reset(
            TASK_STATUS_SUBMIT_FAILED
        )
        schd.pool.compute_runahead(force=True)
        assert int(str(schd.pool.runahead_limit_point)) == 4

        # ... but failed ones don't. Go figure.
        schd.pool.get_task(point('0001'), 'a').state.reset(
            TASK_STATUS_FAILED
        )
        schd.pool.compute_runahead(force=True)
        if compat_mode == 'compat-mode':
            assert int(str(schd.pool.runahead_limit_point)) == 5
        else:
            assert int(str(schd.pool.runahead_limit_point)) == 4  # no change

        # mark cycle 1 as complete
        # (via task message so the task gets removed before runahead compute)
        schd.task_events_mgr.process_message(
            schd.pool.get_task(point('0001'), 'a'),
            logging.INFO,
            TASK_OUTPUT_SUCCEEDED
        )
        schd.pool.compute_runahead(force=True)
        assert int(str(schd.pool.runahead_limit_point)) == 5  # +1


async def test_compute_runahead_with_no_tasks(flow, scheduler, run):
    """It should handle the case of an empty workflow.

    See https://github.com/cylc/cylc-flow/issues/6225
    """
    id_ = flow(
        {
            'scheduling': {
                'initial cycle point': '2000',
                'graph': {'R1': 'foo'},
            },
        }
    )
    schd = scheduler(id_, startcp='2002', paused_start=False)
    async with run(schd):
        assert schd.pool.compute_runahead() is False
        assert schd.pool.runahead_limit_point is None
        assert schd.pool.get_tasks() == []


async def test_compute_runahead_with_no_sequences(
    flow, scheduler, start, run, complete
):
    """It should handle no sequences within the start-stop cycle range.

    See https://github.com/cylc/cylc-flow/issues/6154
    """
    cfg = {
        'scheduling': {
            'cycling mode': 'integer',
            'initial cycle point': '1',
            'graph': {
                'P1': 'foo[-P1] => foo',
            },
        },
    }
    id_ = flow(cfg)
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        await complete(schd, '2/foo')

    cfg['scheduling']['graph']['R1'] = cfg['scheduling']['graph']['P1']
    cfg['scheduling']['graph'].pop('P1')
    flow(cfg, workflow_id=id_)

    schd = scheduler(id_, paused_start=False)
    async with start(schd):
        schd.pool.compute_runahead()
        assert schd.pool.runahead_limit_point == IntegerPoint('3')


@pytest.mark.parametrize('rhlimit', ['P2D', 'P2'])
@pytest.mark.parametrize('compat_mode', ['compat-mode', 'normal-mode'])
async def test_runahead_future_trigger(
    flow,
    scheduler,
    start,
    monkeypatch,
    rhlimit,
    compat_mode,
):
    """Equivalent time interval and cycle count runahead limits should yield
    the same limit point, even if there is a future trigger.

    See https://github.com/cylc/cylc-flow/pull/5893
    """
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
            'cycle point format': 'CCYYMMDD',
        },
        'scheduling': {
            'initial cycle point': '2001',
            'runahead limit': rhlimit,
            'graph': {
                'P1D': '''
                    a
                    a[+P1D] => b
                ''',
            },
        }
    })

    monkeypatch.setattr(
        'cylc.flow.flags.cylc7_back_compat',
        compat_mode == 'compat-mode',
    )
    schd = scheduler(id_,)
    async with start(schd, level=logging.DEBUG):
        assert str(schd.pool.runahead_limit_point) == '20010103'
        schd.pool.release_runahead_tasks()
        for itask in schd.pool.get_tasks():
            schd.pool.spawn_on_output(itask, 'succeeded')
        # future trigger raises the limit by one cycle point
        assert str(schd.pool.runahead_limit_point) == '20010104'


@pytest.fixture(scope='module')
async def mod_blah(
    mod_flow: Callable, mod_scheduler: Callable, mod_run: Callable
) -> 'Scheduler':
    """Return a scheduler for interrogating its task pool.

    This is module-scoped so faster than example_flow, but should only be used
    where the test does not mutate the state of the scheduler or task pool.
    """

    config = {
        'scheduler': {
            'allow implicit tasks': 'True',
            'cycle point format': '%Y',
        },
        'scheduling': {
            'initial cycle point': '0001',
            'runahead limit': 'P1Y',
            'graph': {
                'P1Y': 'a'
            },
        }
    }
    id_ = mod_flow(config)
    schd: 'Scheduler' = mod_scheduler(id_, paused_start=True)
    async with mod_run(schd):
        yield schd


@pytest.mark.parametrize(
    'status, expected',
    [
        # (Status, Are we expecting an update?)
        (TASK_STATUS_WAITING, False),
        (TASK_STATUS_EXPIRED, False),
        (TASK_STATUS_PREPARING, False),
        (TASK_STATUS_SUBMIT_FAILED, False),
        (TASK_STATUS_SUBMITTED, False),
        (TASK_STATUS_RUNNING, False),
        (TASK_STATUS_FAILED, True),
        (TASK_STATUS_SUCCEEDED, True)
    ]
)
async def test_runahead_c7_compat_task_state(
    status,
    expected,
    mod_blah,
    monkeypatch,
):
    """For each task status check whether changing the oldest task
    to that status will cause compute_runahead to make a change.

    Compat mode: Cylc 7 ignored failed tasks but not submit-failed!

    """

    def max_cycle(tasks):
        return max([int(t.tokens.get("cycle")) for t in tasks])

    monkeypatch.setattr(
        'cylc.flow.flags.cylc7_back_compat', True)
    monkeypatch.setattr(
        'cylc.flow.task_events_mgr.TaskEventsManager._insert_task_job',
        lambda *_: True)

    mod_blah.pool.compute_runahead()
    before_pt = max_cycle(mod_blah.pool.get_tasks())
    before = mod_blah.pool.runahead_limit_point
    itask = mod_blah.pool.get_task(ISO8601Point(f'{before_pt - 2:04}'), 'a')
    itask.state_reset(status, is_queued=False)
    mod_blah.pool.compute_runahead()
    after = mod_blah.pool.runahead_limit_point
    assert bool(before != after) == expected


async def test_fast_respawn(
    example_flow: 'Scheduler',
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Immediate re-spawn of removed tasks is not allowed.

    An immediate DB update is required to stop the respawn.
    https://github.com/cylc/cylc-flow/pull/6067

    """
    task_pool = example_flow.pool

    # find task 1/foo in the pool
    foo = task_pool.get_task(IntegerPoint("1"), "foo")

    # remove it from the pool
    task_pool.remove(foo)
    assert foo not in task_pool.get_tasks()

    # attempt to spawn it again
    itask = task_pool.spawn_task("foo", IntegerPoint("1"), {1})
    assert itask is None
    assert "Not respawning 1/foo - task was removed" in caplog.text


async def test_remove_active_task(
    example_flow: 'Scheduler',
    log_filter: Callable,
) -> None:
    """Test warning on removing an active task."""

    task_pool = example_flow.pool

    # find task 1/foo in the pool
    foo = task_pool.get_task(IntegerPoint("1"), "foo")

    foo.state_reset(TASK_STATUS_RUNNING)
    task_pool.remove(foo, "request")
    assert foo not in task_pool.get_tasks()

    assert log_filter(
        regex=(
            "1/foo.*removed from active task pool:"
            " request - active job orphaned"
        ),
        level=logging.WARNING
    )


async def test_remove_by_suicide(
    flow,
    scheduler,
    start,
    log_filter
):
    """Test task removal by suicide trigger.

    * Suicide triggers should remove tasks from the pool.
    * It should be possible to bring them back by manually triggering them.
    * Removing a task manually (cylc remove) should work the same.
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '''
                    a? & b
                    a:failed? => !b
                '''
            },
        }
    })
    schd: 'Scheduler' = scheduler(id_)
    async with start(schd, level=logging.DEBUG) as log:
        # it should start up with 1/a and 1/b
        assert schd.pool.get_task_ids() == {"1/a", "1/b"}
        a = schd.pool.get_task(IntegerPoint("1"), "a")

        # mark 1/a as failed and ensure 1/b is removed by suicide trigger
        schd.pool.spawn_on_output(a, TASK_OUTPUT_FAILED)
        assert log_filter(
            regex="1/b.*removed from active task pool: suicide trigger"
        )
        assert schd.pool.get_task_ids() == {"1/a"}

        # ensure that we are able to bring 1/b back by triggering it
        log.clear()
        schd.pool.force_trigger_tasks(['1/b'], ['1'])
        assert log_filter(
            regex='1/b.*added to active task pool',
        )

        # remove 1/b by request (cylc remove)
        await commands.run_cmd(
            commands.remove_tasks(schd, ['1/b'], [FLOW_ALL])
        )
        assert log_filter(
            regex='1/b.*removed from active task pool: request',
        )

        # ensure that we are able to bring 1/b back by triggering it
        log.clear()
        schd.pool.force_trigger_tasks(['1/b'], ['1'])
        assert log_filter(
            regex='1/b.*added to active task pool',
        )


async def test_set_future_flow(flow, scheduler, start, log_filter):
    """Manually-set outputs for new flow num must be recorded in the DB.

    See https://github.com/cylc/cylc-flow/pull/6186

    To trigger the bug, the flow must be new but the task must have been
    spawned before in an earlier flow.

    """
    # Scenario: after flow 1, set c1:succeeded in a future flow so
    # when b succeeds in the new flow it will spawn c2 but not c1.
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'cycling mode': 'integer',
            'graph': {
                'R1': 'b => c1 & c2',
            },
        },
    })
    schd: 'Scheduler' = scheduler(id_)
    async with start(schd, level=logging.DEBUG):
        assert schd.pool.get_task(IntegerPoint("1"), "b") is not None, (
            '1/b should be spawned on startup'
        )

        # set b, c1, c2 succeeded in flow 1
        schd.pool.set_prereqs_and_outputs(
            ['1/b', '1/c1', '1/c2'], prereqs=[], outputs=[], flow=[1]
        )
        schd.workflow_db_mgr.process_queued_ops()

        # set task c1:succeeded in flow 2
        schd.pool.set_prereqs_and_outputs(
            ['1/c1'], prereqs=[], outputs=[], flow=[2]
        )
        schd.workflow_db_mgr.process_queued_ops()

        # set b:succeeded in flow 2 and check downstream spawning
        schd.pool.set_prereqs_and_outputs(
            ['1/b'], prereqs=[], outputs=[], flow=[2]
        )
        assert schd.pool.get_task(IntegerPoint("1"), "c1") is None, (
            '1/c1 (flow 2) should not be spawned after 1/b:succeeded'
        )
        assert schd.pool.get_task(IntegerPoint("1"), "c2") is not None, (
            '1/c2 (flow 2) should be spawned after 1/b:succeeded'
        )


async def test_trigger_queue(one, run, db_select, complete):
    """It should handle triggering tasks in the queued state.

    Triggering a queued task with a new flow number should result in the
    task running with merged flow numbers.

    See https://github.com/cylc/cylc-flow/pull/6241
    """
    async with run(one):
        # the workflow should start up with one task in the original flow
        task = one.pool.get_tasks()[0]
        assert task.state(TASK_STATUS_WAITING, is_queued=True)
        assert task.flow_nums == {1}

        # trigger this task even though is already queued in flow 1
        one.pool.force_trigger_tasks([task.identity], '2')

        # the merged flow should continue
        one.resume_workflow()
        await complete(one, timeout=2)
        assert db_select(one, False, 'task_outputs', 'flow_nums') == [
            ('[1, 2]',),
            ('[1]',),
        ]


async def test_reload_xtriggers(flow, scheduler, start):
    """It should rebuild xtriggers when the workflow is reloaded.

    See https://github.com/cylc/cylc-flow/pull/6263
    """
    config = {
        'scheduling': {
            'initial cycle point': '2000',
            'graph': {
                'R1': '''
                    @a => foo
                    @b => foo
                '''
            },
            'xtriggers': {
                'a': 'wall_clock(offset="P0D")',
                'b': 'wall_clock(offset="P5D")',
            },
        }
    }
    id_ = flow(config)
    schd: Scheduler = scheduler(id_)

    def list_xtrig_mgr():
        """List xtrigs from the xtrigger_mgr."""
        return {
            key: repr(value)
            for key, value in schd.xtrigger_mgr.xtriggers.functx_map.items()
        }

    async def list_data_store():
        """List xtrigs from the data_store_mgr."""
        await schd.update_data_structure()
        return {
            value.label: key
            for key, value in schd.data_store_mgr.data[schd.tokens.id][
                TASK_PROXIES
            ][
                schd.tokens.duplicate(cycle='20000101T0000Z', task='foo').id
            ].xtriggers.items()
        }

    async with start(schd):
        # check xtrigs on startup
        assert list_xtrig_mgr() == {
            'a': '<SubFuncContext wall_clock(offset=P0D):10.0>',
            'b': '<SubFuncContext wall_clock(offset=P5D):10.0>',
        }
        assert await list_data_store() == {
            'a': 'wall_clock(trigger_time=946684800)',
            'b': 'wall_clock(trigger_time=947116800)',
        }

        # remove @a
        config['scheduling']['xtriggers'].pop('a')
        # modify @b
        config['scheduling']['xtriggers']['b'] = 'wall_clock(offset="PT12H")'
        # add @c
        config['scheduling']['xtriggers']['c'] = 'wall_clock(offset="PT1H")'
        config['scheduling']['graph']['R1'] = config['scheduling']['graph'][
            'R1'
        ].replace('@a', '@c')

        # reload
        flow(config, workflow_id=id_)
        await commands.run_cmd(commands.reload_workflow(schd))

        # check xtrigs post-reload
        assert list_xtrig_mgr() == {
            'b': '<SubFuncContext wall_clock(offset=PT12H):10.0>',
            'c': '<SubFuncContext wall_clock(offset=PT1H):10.0>',
        }
        assert await list_data_store() == {
            'b': 'wall_clock(trigger_time=946728000)',
            'c': 'wall_clock(trigger_time=946688400)',
        }


@pytest.mark.parametrize('expire_type', ['clock-expire', 'manual'])
async def test_expire_dequeue_with_retries(
    flow, scheduler, start, expire_type
):
    """An expired waiting task should be removed from any queues.

    See https://github.com/cylc/cylc-flow/issues/6284
    """
    conf = {
        'scheduling': {
            'initial cycle point': '2000',

            'graph': {
                'R1': 'foo'
            },
        },
        'runtime': {
            'foo': {
                'execution retry delays': 'PT0S'
            }
        }
    }

    if expire_type == 'clock-expire':
        conf['scheduling']['special tasks'] = {'clock-expire': 'foo(PT0S)'}
        method = lambda schd: schd.pool.clock_expire_tasks()
    else:
        method = lambda schd: schd.pool.set_prereqs_and_outputs(
            ['2000/foo'], prereqs=[], outputs=['expired'], flow=['1']
        )

    id_ = flow(conf)
    schd = scheduler(id_)
    schd: Scheduler
    async with start(schd):
        itask = schd.pool.get_tasks()[0]

        # the task should start as "waiting(queued)"
        assert itask.state(TASK_STATUS_WAITING, is_queued=True)

        # expire the task via whichever method we are testing
        method(schd)

        # the task should enter the "expired" state
        assert itask.state(TASK_STATUS_EXPIRED, is_queued=False)

        # the task should also have been removed from the queue
        assert not schd.pool.task_queue_mgr.remove_task(itask)


async def test_downstream_complete_before_upstream(
    flow, scheduler, start, db_select
):
    """It should handle an upstream task completing before a downstream task.

    See https://github.com/cylc/cylc-flow/issues/6315
    """
    id_ = flow(
        {
            'scheduling': {
                'graph': {
                    'R1': 'a => b',
                },
            },
        }
    )
    schd = scheduler(id_)
    async with start(schd):
        # 1/a should be pre-spawned (parentless)
        a_1 = schd.pool.get_task(IntegerPoint('1'), 'a')
        assert a_1

        # spawn 1/b (this can happens as the result of request e.g. trigger)
        b_1 = schd.pool.spawn_task('b', IntegerPoint('1'), {1})
        schd.pool.add_to_pool(b_1)
        assert b_1

        # mark 1/b as succeeded
        schd.task_events_mgr.process_message(b_1, 'INFO', 'succeeded')

        # 1/b should be removed from the pool (completed)
        assert schd.pool.get_tasks() == [a_1]

        # as a side effect the DB should have been updated
        assert (
            TASK_OUTPUT_SUCCEEDED
            in db_select(
                schd,
                # "False" means "do not run the DB update before checking it"
                False,  # do not change this to "True"
                'task_outputs',
                'outputs',
                name='b',
                cycle='1',
            )[0][0]
        )

        # mark 1/a as succeeded
        schd.task_events_mgr.process_message(a_1, 'INFO', 'succeeded')

        # 1/a should be removed from the pool (completed)
        # 1/b should not be re-spawned by the success of 1/a
        assert schd.pool.get_tasks() == []


async def test_job_insert_on_crash(one_conf, flow, scheduler, start):
    """Ensure that a job can be inserted if its config is not known.

    It is possible, though very difficult, to create the circumstances where
    the configuration for the latest job is not held in `itask.jobs`.

    This should not happen under normal circumstances, but should be handled
    elegantly if it does occur.

    See https://github.com/cylc/cylc-flow/issues/6314
    """
    id_ = flow(one_conf)
    schd: Scheduler = scheduler(id_, run_mode='live')
    async with start(schd):
        task_1 = schd.pool.get_tasks()[0]

        # make it look like the task submitted but without storing the job
        # config in TaskProxy.jobs
        task_1.submit_num += 1
        task_1.state.reset('preparing')
        schd.task_events_mgr.process_message(
            task_1,
            'INFO',
            'submitted',
        )

        # the task state should be updated correctly
        assert task_1.state.status == 'submitted'

        # and a job entry should be added
        assert len(task_1.jobs) == 1


async def test_start_tasks(
    flow,
    scheduler,
    start,
    log_filter,
    capture_submission,
):
    """Check starting from "start-tasks" with and without clock-triggers.

    """
    id_ = flow(
        {
            'scheduler': {
                'cycle point format': '%Y',
            },
            'scheduling': {
                'initial cycle point': '2040',
                'runahead limit': 'P0Y',
                'xtriggers': {
                    'wall_clock_satisfied': "wall_clock(offset='-P100Y')"
                },
                'graph': {
                    'P1Y': """
                        foo
                        @wall_clock => bar
                        @wall_clock_satisfied => baz
                        qux
                    """
                }
            }
        }
    )
    schd = scheduler(
        id_,
        starttask=['2050/foo', '2050/bar', '2050/baz'],
        paused_start=False
    )

    async with start(schd):
        # capture any job submissions
        submitted_tasks = capture_submission(schd)
        assert submitted_tasks == set()

        # It should start up with:
        # - 2050/foo and 2051/foo (spawned to runahead limit)
        # - 2050/bar waiting on its (unsatisfied) clock-trigger
        # - 2050/baz waiting on its (satisfied) clock-trigger
        # - no qux instances (not listed as a start-task)
        itasks = schd.pool.get_tasks()
        assert (
            set(itask.identity for itask in itasks) == set([
                "2050/foo",
                "2051/foo",
                "2050/bar",
                "2050/baz",
            ])
        )

        # Check xtriggers
        for itask in itasks:
            schd.pool.xtrigger_mgr.call_xtriggers_async(itask)
            schd.pool.rh_release_and_queue(itask)

        # Release tasks that are ready to run.
        schd.release_tasks_to_run()

        # It should submit 2050/foo, 2051/foo, 2050/baz
        # It should not submit 2050/bar (waiting on clock trigger)
        assert (
            set(itask.identity for itask in submitted_tasks) == set([
                "2050/foo",
                "2051/foo",
                "2050/baz",
            ])
        )

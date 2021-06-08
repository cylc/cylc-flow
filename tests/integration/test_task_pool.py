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
import logging
import pytest
from pytest import param
from typing import Callable, Iterable, List, Tuple, Union

from cylc.flow.cycling import PointBase
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.scheduler import Scheduler


EXAMPLE_FLOW_CFG = {
    'scheduler': {
        'allow implicit tasks': True
    },
    'scheduling': {
        'cycling mode': 'integer',
        'initial cycle point': 1,
        'final cycle point': 4,
        'graph': {
            'P1': 'foo & bar',
            'R1/2': 'foo[1] => pub'  # pub.2 doesn't spawn at start
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
    """Helper function to return sorted task identities ("{name}.{point}")
    from a list of  (name, point) tuples."""
    return sorted(f'{name}.{point}' for name, point in name_point_list)


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
    schd: Scheduler = mod_scheduler(reg)
    async with mod_run(schd):
        pass
    return schd


@pytest.fixture
async def example_flow(
    flow: Callable, scheduler: Callable, caplog: pytest.LogCaptureFixture
) -> Scheduler:
    """Return a scheduler for interrogating its task pool.

    This is function-scoped so slower than mod_example_flow; only use this
    when the test mutates the scheduler or task pool.
    """
    # The run(schd) fixture doesn't work for modifying the DB, so have to
    # set up caplog and do schd.install()/.initialise()/.configure() instead
    caplog.set_level(logging.INFO, CYLC_LOG)
    reg = flow(EXAMPLE_FLOW_CFG)
    schd: Scheduler = scheduler(reg)
    await schd.install()
    await schd.initialise()
    await schd.configure()
    return schd


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'items, expected_task_ids, expected_bad_items, expected_warnings',
    [
        param(
            ['foo'], ['foo.1'], [], [],
            id="Basic"
        ),
        param(
            ['*.1'], ['foo.1', 'bar.1'], [], [],
            id="Name glob"
        ),
        param(
            ['FAM.1'], ['bar.1'], [], [],
            id="Family name"
        ),
        param(
            ['foo.*'], ['foo.1'], [], [],
            id="Point glob"
        ),
        param(
            ['*:waiting'], ['foo.1', 'bar.1'], [], [],
            id="Task state"
        ),
        param(
            ['foo.2'], [], ['foo.2'], ["No active tasks matching: foo.2"],
            id="Task not yet spawned"
        ),
        param(
            ['foo.1', 'bar.2'], ['foo.1'], ['bar.2'],
            ["No active tasks matching: bar.2"],
            id="Multiple items"
        ),
        param(
            ['grogu.1', 'grogu.*'], [], ['grogu.1', 'grogu.*'],
            ["No active tasks matching: grogu.1",
             "No active tasks matching: grogu.*"],
            id="No such task"
        ),
        param(
            [], ['foo.1', 'bar.1'], [], [],
            id="No items given - get all tasks"
        )
    ]
)
async def test_filter_task_proxies(
    items: List[str],
    expected_task_ids: List[str],
    expected_bad_items: List[str],
    expected_warnings: List[str],
    mod_example_flow: Scheduler, caplog: pytest.LogCaptureFixture
) -> None:
    """Test TaskPool.filter_task_proxies().

    Params:
        items: Arg passed to filter_task_proxies().
        expected_task_ids: IDs of the TaskProxys that are expected to be
            returned, of the form "{name}.{point}".
        expected_bad_items: Expected to be returned.
        expected_warnings: Expected to be logged.
    """
    caplog.set_level(logging.WARNING, CYLC_LOG)
    task_pool = mod_example_flow.pool

    itasks, bad_items = task_pool.filter_task_proxies(items)
    task_ids = [itask.identity for itask in itasks]
    assert sorted(task_ids) == sorted(expected_task_ids)
    assert sorted(bad_items) == sorted(expected_bad_items)
    assert_expected_log(caplog, expected_warnings)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'items, expected_task_ids, expected_warnings',
    [
        param(
            ['foo.4'], ['foo.4'], [],
            id="Basic"
        ),
        param(
            ['foo'], [], ["foo - task to spawn must have a cycle point"],
            id="No cycle point given"
        ),
        param(
            ['*.2'], ['foo.2', 'bar.2', 'pub.2'], [],
            id="Name glob"
        ),
        param(
            ['FAM.2'], ['bar.2'], [],
            id="Family name"
        ),
        param(
            ['foo.*'], [], ["No matching tasks found: foo.*"],
            id="Point glob not allowed"
        ),
        param(
            ['grogu.1'], [], ["No matching tasks found: grogu.1"],
            id="No such task"
        ),
        param(
            ['foo.4', 'bar.2', 'grogu.1'], ['foo.4', 'bar.2'],
            ["No matching tasks found: grogu.1"],
            id="Multiple items"
        ),
        param(
            ['foo.5', 'pub.1'], [],
            ["Invalid cycle point for task: foo, 5",
             "Invalid cycle point for task: pub, 1"],
            id="Task not in graph at given cycle point"
        ),
        param(
            ['foo.1:badger'], ['foo.1'], [],
            id="Task state is ignored"
        ),
        param([], [], [], id="No items given")
    ]
)
async def test_match_taskdefs(
    items: List[str],
    expected_task_ids: List[str],
    expected_warnings: List[str],
    mod_example_flow: Scheduler, caplog: pytest.LogCaptureFixture
) -> None:
    """Test TaskPool.match_taskdefs().

    Params:
        items: Arg passed to match_taskdefs().
        ignore_state: Arg passed to match_taskdefs().
        expected_task_ids: Expected IDs of the tasks in the dict that gets
            returned, of the form "{name}.{point}".
        expected_warnings: Expected to be logged.
    """
    caplog.set_level(logging.WARNING, CYLC_LOG)
    task_pool = mod_example_flow.pool

    n_warnings, task_items = task_pool.match_taskdefs(items)
    assert get_task_ids(task_items) == sorted(expected_task_ids)

    logged_warnings = assert_expected_log(caplog, expected_warnings)
    assert n_warnings == len(logged_warnings)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'items, expected_tasks_to_hold_ids, expected_warnings',
    [
        param(
            ['foo.1', 'foo.2'], ['foo.1', 'foo.2'], [],
            id="Active & future tasks"
        ),
        param(
            ['*.1', '*.2'], ['foo.1', 'bar.1'],
            ["No active tasks matching: *.2"],
            id="Name globs hold active tasks only"
        ),
        param(
            ['FAM.1', 'FAM.2'], ['bar.1'],
            ["No active tasks in the family 'FAM' matching: FAM.2"],
            id="Family names hold active tasks only"
        ),
        param(
            ['foo.*', 'bar', 'pub', 'grogu.*'], ['foo.1', 'bar.1'],
            ["No active instances of task: pub",
             "No active tasks matching: grogu.*"],
            id="Point globs/point omitted hold active tasks only"
        ),
        param(
            ['grogu.1', 'foo.H', 'foo.5', 'pub.1'], [],
            ["No matching tasks found: grogu",
             "foo.H - invalid cycle point: H",
             "Invalid cycle point for task: foo, 5",
             "Invalid cycle point for task: pub, 1"],
            id="Non-existent task name or invalid cycle point"
        ),
        param(
            ['foo:waiting', 'foo.1:failed', 'bar.2:waiting'], ['foo.1'],
            ["No active tasks matching: foo.1:failed",
             "No active tasks matching: bar.2:waiting"],
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
            the TaskPool.tasks_to_hold set, of the form "{name}.{point}".
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


@pytest.mark.asyncio
async def test_release_held_tasks(
    example_flow: Scheduler, db_select: Callable
) -> None:
    """Test TaskPool.release_held_tasks().

    For a workflow with held active tasks foo.1 & bar.1, and held future task
    pub.2.

    We skip testing the matching logic here because it would be slow using the
    function-scoped example_flow fixture, and it would repeat what is covered
    in test_hold_tasks().
    """
    # Setup
    task_pool = example_flow.pool
    task_pool.hold_tasks(['foo.1', 'bar.1', 'pub.2'])
    for itask in task_pool.get_all_tasks():
        assert itask.state.is_held is True
    expected_tasks_to_hold_ids = sorted(['foo.1', 'bar.1', 'pub.2'])
    assert get_task_ids(task_pool.tasks_to_hold) == expected_tasks_to_hold_ids
    db_tasks_to_hold = db_select(example_flow, True, 'tasks_to_hold')
    assert get_task_ids(db_tasks_to_hold) == expected_tasks_to_hold_ids

    # Test
    task_pool.release_held_tasks(['foo.1', 'pub.2'])
    for itask in task_pool.get_all_tasks():
        hold_expected = itask.identity == 'bar.1'
        assert itask.state.is_held is hold_expected

    expected_tasks_to_hold_ids = sorted(['bar.1'])
    assert get_task_ids(task_pool.tasks_to_hold) == expected_tasks_to_hold_ids

    db_tasks_to_hold = db_select(example_flow, True, 'tasks_to_hold')
    assert get_task_ids(db_tasks_to_hold) == expected_tasks_to_hold_ids


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'hold_after_point, expected_held_task_ids',
    [
        (0, ['foo.1', 'bar.1']),
        (1, [])
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

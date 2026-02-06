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

"""Test workflow configuration changes.

The tests in this module cover configuration changes made via reload/restart.
"""


import re
from typing import TYPE_CHECKING, Literal

import pytest
from pytest import param

from cylc.flow import commands
from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_WAITING,
)


if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler


def list_tasks(schd, attr='relative_id'):
    return {
        getattr(itask.tokens.duplicate(task_sel=itask.state.status), attr)
        for itask in schd.pool.get_tasks()
    }


async def _test_config_change(
    flow,
    scheduler,
    start_or_run,
    change_type: Literal['reload'] | Literal['restart'],
):
    """Coroutine for testing config changes via either reload or restart.

    This makes it easy to test behaviours which should be the same for both
    reload and restart without duplicating the tests and risking functionality
    drift.

    Usage:
        * Initialise the async coroutine.
        * Yield into it the initial workflow configuration.
        * It will generate a Scheduler object.
        * Yield into it the new config.
        * It will either:
          * Restart the workflow and generate a new Scheduler object,
          * Or reload the workflow and yield the original one again.

    """
    config: dict = yield
    id_ = flow(config)
    schd: 'Scheduler' = scheduler(id_, paused_start=False)
    async with start_or_run(schd):
        yield schd

        config: dict = yield
        flow(config, workflow_id=id_)
        if change_type == 'reload':
            await commands.run_cmd(commands.reload_workflow(schd))
            yield schd
            return

    schd = scheduler(id_, paused_start=False)
    async with start_or_run(schd):
        yield schd


@pytest.mark.parametrize('change_type', ('reload', 'restart'))
async def test_graph_change_handling(
    flow,
    scheduler,
    start,
    db_select,
    caplog,
    change_type: Literal['reload'] | Literal['restart'],
):
    """It should hadle graph changes made by reloads or restarts.

    * If tasks are added by graph change, the added tasks should be logged (if
      reloading, the list cannot be easily determined if restarting).
    * If tasks are removed by graph change, they should be logged, killed and
      removed.
    """
    test_generator = _test_config_change(flow, scheduler, start, change_type)
    config = {
        'scheduling': {
            'graph': {'R1': 'waiting & running & failed & foo'},
        },
        # prevent "running" from completing on the first main loop iteration
        'runtime': {
            'running': {'simulation': {'default run length': 'PT1H'}},
        },
    }

    # start the workflow
    await anext(test_generator)
    schd = await test_generator.asend(config)

    # all four tasks should be in the pool
    assert list_tasks(schd) == {
        '1/waiting',
        '1/running',
        '1/failed',
        '1/foo',
    }

    # put them into various states
    schd.pool._get_task_by_id('1/waiting').state_reset(is_held=True)
    schd.pool._get_task_by_id('1/foo').state_reset(is_held=True)
    schd.pool._get_task_by_id('1/running').state_reset(TASK_STATUS_RUNNING)
    schd.pool._get_task_by_id('1/failed').state_reset(
        TASK_STATUS_FAILED, is_held=True
    )

    # and ensure they are written to the database
    await schd._main_loop()
    assert set(
        db_select(schd, True, 'task_pool', 'cycle', 'name', 'status')
    ) == {
        ('1', 'foo', TASK_STATUS_WAITING),
        ('1', 'waiting', TASK_STATUS_WAITING),
        ('1', 'running', TASK_STATUS_RUNNING),
        ('1', 'failed', TASK_STATUS_FAILED),
    }

    # remove "bar" from the config and reload
    config['scheduling']['graph']['R1'] = 'foo & bar'
    await anext(test_generator)
    schd = await test_generator.asend(config)

    # the "orphaned" tasks should not be in the pool
    assert list_tasks(schd) == {'1/foo'}

    # the "orphaned" tasks should not be in the database
    await schd._main_loop()
    assert db_select(schd, True, 'task_pool', 'cycle', 'name', 'status') == [
        ('1', 'foo', TASK_STATUS_WAITING)
    ]

    # the graph changes should have been logged
    record = None
    for record in caplog.records:
        if f'Graph changed due to {change_type}' in record.message:
            break

    assert re.search(r'\* 1/failed.*:failed', record.message)
    assert re.search(r'\* 1/running.*:running', record.message)
    assert re.search(r'\* 1/waiting.*:waiting', record.message)

    if change_type == 'reload':
        # NOTE: we cannot easily determine added tasks when restarting
        assert re.search('Added tasks', record.message)
        assert re.search(r'\* bar', record.message)


@pytest.mark.parametrize('change_type', ('reload', 'restart'))
async def test_task_pool_logic(flow, scheduler, run, change_type, complete):
    """Test the evolution of the task pool across graph changes."""
    test_generator = _test_config_change(flow, scheduler, run, change_type)
    await anext(test_generator)

    # start the workflow
    schd = await test_generator.asend(
        {'scheduling': {'graph': {'R1': 'a => b'}}}
    )
    await anext(test_generator)

    # run up to 1/b:succeeded
    await complete(schd, '1/a', timeout=3)
    assert list_tasks(schd) == {'1/b'}

    # change the graph
    # - b
    # + c
    # + d
    schd = await test_generator.asend(
        {'scheduling': {'graph': {'R1': 'c => a => d'}}}
    )

    # b should be removed - https://github.com/cylc/cylc-flow/issues/7198
    # a & b should not be added (SoD status quo)
    assert list_tasks(schd) == set()


@pytest.mark.parametrize('orphan', (True, False))
async def test_missing_platform_config(
    flow,
    scheduler,
    start,
    one_conf,
    monkeypatch,
    log_filter,
    orphan,
):
    """It handles PlatformLookupErrors raised during restart.

    Cylc needs to associate any jobs with were submitted or running when the
    workflow was shut down with the platforms recorded in the DB in order to
    poll them for status updates, and permit any future operations.

    If the platform has been removed from the global config since the workflow
    was shut down, the Scheduler should bail on startup as this is not a
    situation we can currently manage.

    However, if the task is an orphan (a task removed by reload) i.e, one we
    are going to remove anyway, this isn't a critical error.
    """
    one_conf.update({
        # prevent the scheduler shutting down on the first main loop iteration
        'runtime': {
            'root': {'simulation': {'default run length': 'PT1H'}},
        },
    })
    test_generator = _test_config_change(flow, scheduler, start, 'restart')

    # start the workflow
    await anext(test_generator)
    schd = await test_generator.asend(one_conf)
    await schd._main_loop()  # ensure the task pool is written to the DB
    await anext(test_generator)

    if orphan:
        # make the sole task in this workflow an orphan
        one_conf['scheduling']['graph']['R1'] = 'new-task'

    # force a PlatformLookupError upon restart
    def _get_platform(*_args, **_kwargs):
        raise PlatformLookupError('FOO')
    monkeypatch.setattr('cylc.flow.task_pool.get_platform', _get_platform)

    # restart the workflow
    schd = await test_generator.asend(one_conf)

    # a PlatformLookupError should have been raised
    msg = r'platforms are not defined.*\n.*simulation'
    if orphan:
        with pytest.raises(StopAsyncIteration):
            # this error is not critical
            # NOTE: StopAsyncIteration just means the test generator has shut
            # down cleanly
            await anext(test_generator)
        # the undefined platform should still be logged though
        assert log_filter(regex=msg)
    else:
        with pytest.raises(PlatformLookupError, match=msg):
            # this error is criticla: ensure the scheduler bails on startup
            await anext(test_generator)

    # the workflow should refuse to restart, unless the task is orphaned in
    # which case the error should be tolerated (just means we can't issue the
    # kill command but not critical to the workflow)
    assert (
        log_filter(regex='Workflow shutting down - PlatformLookupError')
        is not orphan
    )


@pytest.mark.parametrize('change_type', ('reload', 'restart'))
@pytest.mark.parametrize(
    '''
        graph_1,
        graph_2,
        task_pool_at_startup,
        task_pool_post_spawn,
        task_pool_after_reload_or_restart,
        task_z_prereqs
    ''',
    [
        param(  # Restart after adding a prerequisite to task z
            '''a => z
               b => z''',
            '''a => z
               b => z
               c => z''',
            {
                '1/a:running',
                '1/b:running',
            },
            {
                '1/b:running',
                '1/z:waiting',
            },
            {
                '1/b:running',
                '1/z:waiting',
            },
            [
                {('1', 'a', 'succeeded'): 'satisfied naturally'},
                {('1', 'b', 'succeeded'): False},
                {('1', 'c', 'succeeded'): False},
            ],
            id='added',
        ),
        param(  # Restart after removing a prerequisite from task z
            '''a => z
               b => z
               c => z''',
            '''a => z
               b => z''',
            {
                '1/a:running',
                '1/b:running',
                '1/c:running',
            },
            {
                '1/b:running',
                '1/c:running',
                '1/z:waiting',
            },
            {
                '1/b:running',
                '1/z:waiting',
            },
            [
                {('1', 'a', 'succeeded'): 'satisfied naturally'},
                {('1', 'b', 'succeeded'): False},
            ],
            id='removed',
        ),
    ],
)
async def test_prereq_change(
    flow,
    scheduler,
    start,
    change_type,
    graph_1,
    graph_2,
    task_pool_at_startup,
    task_pool_post_spawn,
    task_pool_after_reload_or_restart,
    task_z_prereqs,
):
    """It should handle graph prerequisites change on reload/restart.

    Prerequisite changes must be applied to tasks already in the pool.
    See https://github.com/cylc/cylc-flow/pull/5334
    """
    test_generator = _test_config_change(flow, scheduler, start, change_type)

    # start the workflow
    await anext(test_generator)
    schd = await test_generator.asend(graph_1)
    await anext(test_generator)

    # Release tasks 1/a and 1/b
    schd.pool.release_runahead_tasks()
    schd.release_tasks_to_run()
    assert (
        list_tasks(schd, 'relative_id_with_selectors') == task_pool_at_startup
    )

    # Mark 1/a as succeeded and spawn 1/z
    task_a = schd.pool.get_tasks()[0]
    schd.pool.task_events_mgr.process_message(task_a, 1, 'succeeded')
    assert (
        list_tasks(schd, 'relative_id_with_selectors') == task_pool_post_spawn
    )

    # Save our progress
    schd.workflow_db_mgr.put_task_pool(schd.pool)

    # Edit the workflow to add a new dependency on "z" then reload/restart
    schd = await test_generator.asend(graph_2)

    # Load jobs from db
    schd.workflow_db_mgr.pri_dao.select_jobs_for_restart(
        schd.data_store_mgr.insert_db_job
    )
    assert (
        list_tasks(schd, 'relative_id_with_selectors')
        == task_pool_after_reload_or_restart
    )

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
    ) == task_z_prereqs

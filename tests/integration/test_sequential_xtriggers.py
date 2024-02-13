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

"""Test interactions with sequential xtriggers."""

import pytest

from cylc.flow.cycling.iso8601 import ISO8601Point


@pytest.fixture()
def sequential(flow, scheduler):
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
            'cycle point format': 'CCYY',
        },
        'scheduling': {
            'runahead limit': 'P2',
            'initial cycle point': '2000',
            'graph': {
                'P1Y': '@wall_clock => foo',
            }
        }
    })

    sequential = scheduler(id_)

    def list_tasks():
        """List the task instance cycle points present in the pool."""
        nonlocal sequential
        return sorted(itask.tokens['cycle'] for itask in sequential.pool.get_all_tasks())

    sequential.list_tasks = list_tasks

    return sequential


async def test_remove(sequential, start):
    """It should spawn the next instance when a task is removed.

    Ensure that removing a task with a sequential xtrigger does not break the
    chain causing future instances to be removed from the workflow.
    """
    async with start(sequential):
        # the scheduler starts with one task in the pool
        assert sequential.list_tasks() == ['2000']

        # it sequentially spawns out to the runahead limit
        for year in range(2000, 2010):
            foo = sequential.pool.get_task(ISO8601Point(f'{year}'), 'foo')
            if foo.state(is_runahead=True):
                break
            sequential.xtrigger_mgr.call_xtriggers_async(foo)
            sequential.pool.spawn_parentless_sequential_xtriggers()
        assert sequential.list_tasks() == [
            '2000',
            '2001',
            '2002',
            '2003',
        ]

        # remove all tasks in the pool
        sequential.pool.remove_tasks(['*'])

        # the next cycle should be automatically spawned
        assert sequential.list_tasks() == ['2004']

        # NOTE: You won't spot this issue in a functional test because the
        # re-spawned tasks are detected as completed and automatically removed.
        # So ATM not dangerous, but potentially inefficient.


async def test_trigger(sequential, start):
    """It should spawn its next instance if triggered ahead of time.

    If you manually trigger a sequentially spawned task before its xtriggers
    have become satisfied, then the sequential spawning chain is broken.

    The task pool should defend against this to ensure that triggering a task
    doesn't cancel it's future instances.
    """
    async with start(sequential):
        assert sequential.list_tasks() == ['2000']

        foo = sequential.pool.get_task(ISO8601Point('2000'), 'foo')
        sequential.pool.force_trigger_tasks([foo.identity], {1})
        foo.state_reset('succeeded')
        sequential.pool.spawn_on_output(foo, 'succeeded')

        assert sequential.list_tasks() == ['2001']


async def test_reload(sequential, start):
    """It should set the is_xtrigger_sequential flag on reload.

    TODO: test that changes to the sequential status in the config get picked
          up on reload
    """
    async with start(sequential):
        # the task should be marked as sequential
        pre_reload = sequential.pool.get_task(ISO8601Point('2000'), 'foo')
        assert pre_reload.is_xtrigger_sequential is True

        # reload the workflow
        sequential.pool.reload_taskdefs(sequential.config)

        # the original task proxy should have been replaced
        post_reload = sequential.pool.get_task(ISO8601Point('2000'), 'foo')
        assert id(pre_reload) != id(post_reload)

        # the new task should be marked as sequential
        assert post_reload.is_xtrigger_sequential is True


# TODO: test that a task is marked as sequential if any of its xtriggers are
# sequential (as opposed to all)?

# TODO: test setting the sequential argument in [scheduling][xtrigger] items
# changes the behaviour

# TODO: test the interaction between "sequential xtriggers default" and the
# sequential argument to [scheduling][xtrigger]
# * Should we be able to override the default by setting sequential=False?
# * Or should that result in a validation error?

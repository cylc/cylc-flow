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

# mypy: disable-error-code=union-attr

"""Test interactions with sequential xtriggers."""

from unittest.mock import patch
import pytest
from cylc.flow.cycling.integer import IntegerPoint

from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.exceptions import XtriggerConfigError
from cylc.flow.scheduler import Scheduler


def list_cycles(schd: Scheduler):
    """List the task instance cycle points present in the pool."""
    return sorted(itask.tokens['cycle'] for itask in schd.pool.get_tasks())


@pytest.fixture()
def sequential(flow, scheduler):
    id_ = flow({
        'scheduler': {
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
    return scheduler(id_)


async def test_remove(sequential: Scheduler, start):
    """It should spawn the next instance when a task is removed.

    Ensure that removing a task with a sequential xtrigger does not break the
    chain causing future instances to be removed from the workflow.
    """
    async with start(sequential):
        # the scheduler starts with one task in the pool
        assert list_cycles(sequential) == ['2000']

        # it sequentially spawns out to the runahead limit
        for year in range(2000, 2010):
            foo = sequential.pool.get_task(ISO8601Point(f'{year}'), 'foo')
            if foo.state(is_runahead=True):
                break
            sequential.xtrigger_mgr.call_xtriggers_async(foo)
            sequential.pool.spawn_parentless_sequential_xtriggers()
        assert list_cycles(sequential) == [
            '2000',
            '2001',
            '2002',
            '2003',
        ]

        # remove all tasks in the pool
        sequential.remove_tasks(['*'])

        # the next cycle should be automatically spawned
        assert list_cycles(sequential) == ['2004']

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
        assert list_cycles(sequential) == ['2000']

        foo = sequential.pool.get_task(ISO8601Point('2000'), 'foo')
        sequential.pool.force_trigger_tasks([foo.identity], {1})
        foo.state_reset('succeeded')
        sequential.pool.spawn_on_output(foo, 'succeeded')

        assert list_cycles(sequential) == ['2000', '2001']


async def test_set(sequential, start):
    """It should spawn its next instance if outputs are set ahead of time.

    If you set outputs of a sequentially spawned task before its xtriggers
    have become satisfied, then the sequential spawning chain is broken.

    The task pool should defend against this to ensure that setting outputs
    doesn't cancel it's future instances and their downstream tasks.
    """
    async with start(sequential):
        assert list_cycles(sequential) == ['2000']

        sequential.pool.get_task(ISO8601Point('2000'), 'foo')
        # set foo:succeeded it should spawn next instance
        sequential.pool.set_prereqs_and_outputs(
            ["2000/foo"], ["succeeded"], None, ['all'])

        assert list_cycles(sequential) == ['2001']


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
        sequential.pool.reload(sequential.config)

        # the original task proxy should have been replaced
        post_reload = sequential.pool.get_task(ISO8601Point('2000'), 'foo')
        assert id(pre_reload) != id(post_reload)

        # the new task should be marked as sequential
        assert post_reload.is_xtrigger_sequential is True


@pytest.mark.parametrize('is_sequential', [True, False])
@pytest.mark.parametrize('xtrig_def', [
    'wall_clock(sequential={})',
    'wall_clock(PT1H, sequential={})',
    'xrandom(1, 1, sequential={})',
])
async def test_sequential_arg_ok(
    flow, scheduler, start, xtrig_def: str, is_sequential: bool
):
    """Test passing the sequential argument to xtriggers."""
    wid = flow({
        'scheduler': {
            'cycle point format': 'CCYY',
        },
        'scheduling': {
            'initial cycle point': '2000',
            'runahead limit': 'P1',
            'xtriggers': {
                'myxt': xtrig_def.format(is_sequential),
            },
            'graph': {
                'P1Y': '@myxt => foo',
            }
        }
    })
    schd: Scheduler = scheduler(wid)
    expected_num_cycles = 1 if is_sequential else 3
    async with start(schd):
        itask = schd.pool.get_task(ISO8601Point('2000'), 'foo')
        assert itask.is_xtrigger_sequential is is_sequential
        assert len(list_cycles(schd)) == expected_num_cycles


def test_sequential_arg_bad(flow, validate):
    """Test validation of 'sequential' arg for custom xtrigger function def"""
    wid = flow({
        'scheduling': {
            'xtriggers': {
                'myxt': 'custom_xt(42)'
            },
            'graph': {
                'R1': '@myxt => foo'
            }
        }
    })

    def xtrig1(x, sequential):
        """This uses 'sequential' without a default value"""
        return True

    def xtrig2(x, sequential='True'):
        """This uses 'sequential' with a default of wrong type"""
        return True

    for xtrig in (xtrig1, xtrig2):
        with patch(
            'cylc.flow.xtrigger_mgr.get_xtrig_func',
            return_value=xtrig
        ):
            with pytest.raises(XtriggerConfigError) as excinfo:
                validate(wid)
            assert (
                "reserved argument 'sequential' with no boolean default"
            ) in str(excinfo.value)


def test_sequential_arg_bad2(flow, validate):
    """Test validation of 'sequential' arg for xtrigger calls"""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2000',
            'xtriggers': {
                'clock': 'wall_clock(sequential=3)',
            },
            'graph': {
                'R1': '@clock => foo',
            },
        },
    })

    with pytest.raises(XtriggerConfigError) as excinfo:
        validate(wid)
    assert (
        "invalid argument 'sequential=3' - must be boolean"
    ) in str(excinfo.value)


@pytest.mark.parametrize('is_sequential', [True, False])
async def test_any_sequential(flow, scheduler, start, is_sequential: bool):
    """Test that a task is marked as sequential if any of its xtriggers are."""
    wid = flow({
        'scheduling': {
            'xtriggers': {
                'xt1': 'custom_xt()',
                'xt2': f'custom_xt(sequential={is_sequential})',
                'xt3': 'custom_xt(sequential=False)',
            },
            'graph': {
                'R1': '@xt1 & @xt2 & @xt3 => foo',
            }
        }
    })

    with patch(
        'cylc.flow.xtrigger_mgr.get_xtrig_func',
        return_value=lambda *a, **k: True
    ):
        schd: Scheduler = scheduler(wid)
        async with start(schd):
            itask = schd.pool.get_task(IntegerPoint('1'), 'foo')
            assert itask.is_xtrigger_sequential is is_sequential


async def test_override(flow, scheduler, start):
    """Test that the 'sequential=False' arg can override a default of True."""
    wid = flow({
        'scheduling': {
            'sequential xtriggers': True,
            'xtriggers': {
                'xt1': 'custom_xt()',
                'xt2': 'custom_xt(sequential=False)',
            },
            'graph': {
                'R1': '''
                    @xt1 => foo
                    @xt2 => bar
                ''',
            }
        }
    })

    with patch(
        'cylc.flow.xtrigger_mgr.get_xtrig_func',
        return_value=lambda *a, **k: True
    ):
        schd: Scheduler = scheduler(wid)
        async with start(schd):
            foo = schd.pool.get_task(IntegerPoint('1'), 'foo')
            assert foo.is_xtrigger_sequential is True
            bar = schd.pool.get_task(IntegerPoint('1'), 'bar')
            assert bar.is_xtrigger_sequential is False

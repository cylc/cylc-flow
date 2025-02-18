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
"""Tests for the behaviour of xtrigger manager."""

import asyncio
from pathlib import Path
from textwrap import dedent

from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.scheduler import Scheduler


async def test_2_xtriggers(flow, start, scheduler, monkeypatch):
    """Test that if an itask has 4 wall_clock triggers with different
    offsets that xtrigger manager gets all of them.

    https://github.com/cylc/cylc-flow/issues/5783

    n.b. Clock 3 exists to check the memoization path is followed,
    and causing this test to give greater coverage.
    Clock 4 & 5 test higher precision offsets than the CPF.
    """
    task_point = 1588636800                # 2020-05-05
    ten_years_ahead = 1904169600           # 2030-05-05
    PT2H35M31S_ahead = 1588646131          # 2020-05-05 02:35:31
    PT2H35M31S_behind = 1588627469         # 2020-05-04 21:24:29
    monkeypatch.setattr(
        'cylc.flow.xtriggers.wall_clock.time',
        lambda: ten_years_ahead - 1
    )
    id_ = flow({
        'scheduler': {
            'cycle point format': 'CCYY-MM-DD',
        },
        'scheduling': {
            'initial cycle point': '2020-05-05',
            'xtriggers': {
                'clock_1': 'wall_clock()',
                'clock_2': 'wall_clock(offset=P10Y)',
                'clock_3': 'wall_clock(offset=P10Y)',
                'clock_4': 'wall_clock(offset=PT2H35M31S)',
                'clock_5': 'wall_clock(offset=-PT2H35M31S)',
            },
            'graph': {
                'R1': '@clock_1 & @clock_2 & @clock_3 &'
                ' @clock_4 & @clock_5 => foo'
            }
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        foo_proxy = schd.pool.get_tasks()[0]
        clock_1_ctx = schd.xtrigger_mgr.get_xtrig_ctx(foo_proxy, 'clock_1')
        clock_2_ctx = schd.xtrigger_mgr.get_xtrig_ctx(foo_proxy, 'clock_2')
        clock_3_ctx = schd.xtrigger_mgr.get_xtrig_ctx(foo_proxy, 'clock_2')
        clock_4_ctx = schd.xtrigger_mgr.get_xtrig_ctx(foo_proxy, 'clock_4')
        clock_5_ctx = schd.xtrigger_mgr.get_xtrig_ctx(foo_proxy, 'clock_5')

        assert clock_1_ctx.func_kwargs['trigger_time'] == task_point
        assert clock_2_ctx.func_kwargs['trigger_time'] == ten_years_ahead
        assert clock_3_ctx.func_kwargs['trigger_time'] == ten_years_ahead
        assert clock_4_ctx.func_kwargs['trigger_time'] == PT2H35M31S_ahead
        assert clock_5_ctx.func_kwargs['trigger_time'] == PT2H35M31S_behind

        schd.xtrigger_mgr.call_xtriggers_async(foo_proxy)
        assert foo_proxy.state.xtriggers == {
            'clock_1': True,
            'clock_2': False,
            'clock_3': False,
            'clock_4': True,
            'clock_5': True,
        }


async def test_1_xtrigger_2_tasks(flow, start, scheduler, mocker):
    """
    If multiple tasks depend on the same satisfied xtrigger, the DB mgr method
    put_xtriggers should only be called once - when the xtrigger gets satisfied

    See [GitHub #5908](https://github.com/cylc/cylc-flow/pull/5908)

    """
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2020',
            'graph': {
                'R1': '@wall_clock => foo & bar'
            }
        }
    })

    schd = scheduler(id_)
    spy = mocker.spy(schd.workflow_db_mgr, 'put_xtriggers')

    async with start(schd):

        # Call the clock trigger via its dependent tasks, to get it satisfied.
        for task in schd.pool.get_tasks():
            # (For clock triggers this is synchronous)
            schd.xtrigger_mgr.call_xtriggers_async(task)

        # It should now be satisfied.
        assert task.state.xtriggers == {'wall_clock': True}

        # Check one put_xtriggers call only, not two.
        assert spy.call_count == 1

        # Note on master prior to GH #5908 the call is made from the
        # scheduler main loop when the two tasks become satisified,
        # resulting in two calls to put_xtriggers. This test fails
        # on master, but with call count 0 (not 2) because the main
        # loop doesn't run in this test.


async def test_xtriggers_restart(flow, start, scheduler, db_select):
    """It should write xtrigger results to the DB and load them on restart."""
    # define a workflow which uses a custom xtrigger
    id_ = flow({
        'scheduling': {
            'xtriggers': {
                'mytrig': 'mytrig()'
            },
            'graph': {
                'R1': '@mytrig => foo'
            },
        }
    })

    # add a custom xtrigger to the workflow
    run_dir = Path(get_workflow_run_dir(id_))
    xtrig_dir = run_dir / 'lib/python'
    xtrig_dir.mkdir(parents=True)
    (xtrig_dir / 'mytrig.py').write_text(dedent('''
        from random import random

        def mytrig(*args, **kwargs):
            # return a different random number each time
            return True, {"x": str(random())}
    '''))

    # start the workflow & run the xtrigger
    schd = scheduler(id_)
    async with start(schd):
        # run all xtriggers
        for task in schd.pool.get_tasks():
            schd.xtrigger_mgr.call_xtriggers_async(task)
        # one xtrigger should have been scheduled to run
        assert len(schd.proc_pool.queuings) + len(schd.proc_pool.runnings) == 1
        # wait for it to return
        for _ in range(50):
            await asyncio.sleep(0.1)
            schd.proc_pool.process()
            if len(schd.proc_pool.runnings) == 0:
                break
        else:
            raise Exception('Process pool did not clear')

    # the xtrigger should be written to the DB
    db_xtriggers = db_select(schd, True, 'xtriggers')
    assert len(db_xtriggers) == 1
    assert db_xtriggers[0][0] == 'mytrig()'
    assert db_xtriggers[0][1].startswith('{"x":')

    # restart the workflow, the xtrigger should *not* run again
    schd = scheduler(id_)
    async with start(schd):
        # run all xtriggers
        for task in schd.pool.get_tasks():
            schd.xtrigger_mgr.call_xtriggers_async(task)
        # the xtrigger should have been loaded from the DB
        # (so no xtriggers should be scheduled to run)
        assert len(schd.proc_pool.queuings) + len(schd.proc_pool.runnings) == 0

    # check the DB to ensure no additional entries have been created
    assert db_select(schd, True, 'xtriggers') == db_xtriggers


async def test_error_in_xtrigger(flow, start, scheduler):
    """Failure in an xtrigger is handled nicely.
    """
    id_ = flow({
        'scheduling': {
            'xtriggers': {
                'mytrig': 'mytrig()'
            },
            'graph': {
                'R1': '@mytrig => foo'
            },
        }
    })

    # add a custom xtrigger to the workflow
    run_dir = Path(get_workflow_run_dir(id_))
    xtrig_dir = run_dir / 'lib/python'
    xtrig_dir.mkdir(parents=True)
    (xtrig_dir / 'mytrig.py').write_text(dedent('''
        def mytrig(*args, **kwargs):
            raise Exception('This Xtrigger is broken')
    '''))

    schd = scheduler(id_)
    async with start(schd) as log:
        foo = schd.pool.get_tasks()[0]
        schd.xtrigger_mgr.call_xtriggers_async(foo)
        for _ in range(50):
            await asyncio.sleep(0.1)
            schd.proc_pool.process()
            if len(schd.proc_pool.runnings) == 0:
                break
        else:
            raise Exception('Process pool did not clear')

        error = log.messages[-1].split('\n')
        assert error[-2] == 'Exception: This Xtrigger is broken'
        assert error[0] == 'ERROR in xtrigger mytrig()'


async def test_1_seq_clock_trigger_2_tasks(flow, start, scheduler):
    """Test that all tasks dependent on a sequential clock trigger continue to
    spawn after the first cycle.

    See https://github.com/cylc/cylc-flow/issues/6204
    """
    id_ = flow({
        'scheduler': {
            'cycle point format': 'CCYY',
        },
        'scheduling': {
            'initial cycle point': '1990',
            'graph': {
                'P1Y': '@wall_clock => foo & bar',
            },
        },
    })
    schd: Scheduler = scheduler(id_)

    async with start(schd):
        start_task_pool = schd.pool.get_task_ids()
        assert start_task_pool == {'1990/foo', '1990/bar'}

        for _ in range(3):
            await schd._main_loop()

        assert schd.pool.get_task_ids() == start_task_pool.union(
            f'{year}/{name}'
            for year in range(1991, 1994)
            for name in ('foo', 'bar')
        )

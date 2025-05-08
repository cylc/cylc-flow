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
from typing import cast, Iterable

from cylc.flow import commands
from cylc.flow.data_messages_pb2 import PbTaskProxy
from cylc.flow.data_store_mgr import TASK_PROXIES
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
                'R1': (
                    '@clock_1 & @clock_2 & @clock_3 & @clock_4 & @clock_5'
                    ' => foo'
                )
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
    """It should write satisfied xtriggers to the DB and load on restart.

    This checks persistence of xtrigger function results across restarts.

    See also test_set_xtriggers_restart for task dependence on xtriggers.

    """
    id_ = flow({
        'scheduling': {
            'xtriggers': {
                'x100': 'xrandom(100)',  # always succeeds
                'x0': 'xrandom(0)'  # never succeeds
            },
            'graph': {
                'R1': '''
                    @x100 => foo
                    @x0 = > bar
                '''
            },
        }
    })
    # start the workflow & run the xtrigger
    schd = scheduler(id_)
    async with start(schd):
        # run all xtriggers
        for task in schd.pool.get_tasks():
            schd.xtrigger_mgr.call_xtriggers_async(task)
        # two xtriggers should have been scheduled to run
        # and x100 should succeed
        assert len(schd.proc_pool.queuings) + len(schd.proc_pool.runnings) == 2
        # wait for it to return
        for _ in range(50):
            await asyncio.sleep(0.1)
            schd.proc_pool.process()
            if len(schd.proc_pool.runnings) == 0:
                break
        else:
            raise Exception('Process pool did not clear')

    # the satisfied x100 should be written to the DB
    db_xtriggers = db_select(schd, True, 'xtriggers')
    assert len(db_xtriggers) == 1
    assert db_xtriggers[0][0] == 'xrandom(100)'
    assert db_xtriggers[0][1].startswith('{"COLOR":')  # (xrandom result dict)

    # restart the workflow, the xtrigger should *not* run again
    schd = scheduler(id_)
    async with start(schd):
        # run all xtriggers
        for task in schd.pool.get_tasks():
            schd.xtrigger_mgr.call_xtriggers_async(task)

        # satisfied x100 should have been loaded from the DB
        # so only one xtrigger should be scheduled to run now
        assert len(schd.proc_pool.queuings) + len(schd.proc_pool.runnings) == 1

        # x0 should not be satisfied
        bar = schd.pool._get_task_by_id('1/bar')
        assert not bar.state.xtriggers["x0"]

        # x100 should now be satisfied in the task pool and the datastore
        foo = schd.pool._get_task_by_id('1/foo')
        assert foo.state.xtriggers["x100"]

        await schd.update_data_structure()
        [xtrig] = [
            p
            for t in cast(
                'Iterable[PbTaskProxy]',
                schd.data_store_mgr.data[
                    schd.data_store_mgr.workflow_id
                ][
                    TASK_PROXIES
                ].values()
            )
            for p in t.xtriggers.values()
            if p.label == "x100"
        ]
        assert xtrig.id == "xrandom(100)"
        assert xtrig.satisfied

    # check the DB to ensure no additional entries have been created
    assert db_select(schd, True, 'xtriggers') == db_xtriggers


async def test_set_xtrig_prereq_restart(flow, start, scheduler, db_select):
    """Satisfied xtrigger prerequisites should persist across restart.

    (Task prerequisites can be artificially satisfied by "cylc set").

    See also test_xtriggers_restart, for persistence of xtrigger results.

    """
    id_ = flow({
        'scheduling': {
            'xtriggers': {
                'x0': 'xrandom(0)'  # never succeeds naturally
            },
            'graph': {
                'R1': '''
                    @x0 = > foo & bar
                '''
            },
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        # artificially set dependence of foo on x0
        schd.pool.set_prereqs_and_outputs(
            ['1/foo'], [], ['xtrigger/x0:succeeded'], ['all']
        )

    # the satisfied x0 prerequisite should be written to the DB
    [db_pre] = db_select(schd, True, 'task_prerequisites')
    assert db_pre == ('1', 'foo', '[1]', 'x0', 'xtrigger', 'succeeded', '1')

    # restart the workflow
    schd = scheduler(id_)
    async with start(schd):
        # run all xtriggers
        for task in schd.pool.get_tasks():
            schd.xtrigger_mgr.call_xtriggers_async(task)

        # foo's dependence on x0 should be satisfied from the DB
        # but bar still depends on it so the scheduler should still call it.
        assert len(schd.proc_pool.queuings) + len(schd.proc_pool.runnings) == 1

        # "@x0 => bar" should not be satisfied
        bar = schd.pool._get_task_by_id('1/bar')
        assert not bar.state.xtriggers["x0"]

        # but "x0 => foo" should be, in the task pool and the datastore
        foo = schd.pool._get_task_by_id('1/foo')
        assert foo.state.xtriggers["x0"]

        await schd.update_data_structure()
        xtrigs = [
            (t.id, p)
            for t in cast(
                'Iterable[PbTaskProxy]',
                schd.data_store_mgr.data[
                    schd.data_store_mgr.workflow_id
                ][
                    TASK_PROXIES
                ].values()
            )
            for p in t.xtriggers.values()
        ]
        assert len(xtrigs) == 2
        for (id, xtrig) in xtrigs:
            if id.endswith('foo'):
                assert xtrig.id == "xrandom(0)"
                assert xtrig.satisfied
            elif id.endswith('bar'):
                assert xtrig.id == "xrandom(0)"
                assert not xtrig.satisfied
            else:
                assert False


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


async def test_set_xtrig_prereq_reload(flow, start, scheduler, db_select):
    """Satisfied xtrigger prerequisites should persist across reload.

    (Task prerequisites can be artificially satisfied by "cylc set").

    """
    id_ = flow({
        'scheduling': {
            'xtriggers': {
                'x0': 'xrandom(0)'  # never succeeds naturally
            },
            'graph': {
                'R1': '''
                    @x0 = > foo & bar
                '''
            },
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        # artificially set dependence of foo on x0
        schd.pool.set_prereqs_and_outputs(
            ['1/foo'], [], ['xtrigger/x0:succeeded'], ['all']
        )

        # reload the workflow
        await commands.run_cmd(commands.reload_workflow(schd))

        # run all xtriggers
        for task in schd.pool.get_tasks():
            schd.xtrigger_mgr.call_xtriggers_async(task)

        # foo's dependence on x0 should remain satisfied, but bar still depends
        # on it so the function should still be called by the scheduler.
        assert len(schd.proc_pool.queuings) + len(schd.proc_pool.runnings) == 1

        # "@x0 => bar" should not be satisfied
        bar = schd.pool._get_task_by_id('1/bar')
        assert not bar.state.xtriggers["x0"]

        # but "x0 => foo" should be, in the task pool and the datastore
        foo = schd.pool._get_task_by_id('1/foo')
        assert foo.state.xtriggers["x0"]

        await schd.update_data_structure()
        xtrigs = [
            (t.id, p)
            for t in cast(
                'Iterable[PbTaskProxy]',
                schd.data_store_mgr.data[
                    schd.data_store_mgr.workflow_id
                ][
                    TASK_PROXIES
                ].values()
            )
            for p in t.xtriggers.values()
        ]
        assert len(xtrigs) == 2
        for (id, xtrig) in xtrigs:
            if id.endswith('foo'):
                assert xtrig.id == "xrandom(0)"
                assert xtrig.satisfied
            elif id.endswith('bar'):
                assert xtrig.id == "xrandom(0)"
                assert not xtrig.satisfied
            else:
                assert False


async def test_force_satisfy(flow, start, scheduler, log_filter):
    """It should satisfy valid xtriggers and ignore invalid ones."""
    id_ = flow({
        'scheduling': {
            'xtriggers': {
                'x': 'xrandom(0)'
            },
            'graph': {
                'R1': '@x => foo'
            },
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        foo = schd.pool.get_tasks()[0]

        # check x not satisfied yet
        assert not foo.state.xtriggers['x']  # not satisified

        # force satisfy it
        xtrigs = {
            "x": True,  # it should satisfy this one
            "y": True  # it should just ignore this one
        }
        schd.xtrigger_mgr.force_satisfy(foo, xtrigs)

        assert foo.state.xtriggers['x']  # satisified
        assert log_filter(
            contains=(
                'xtrigger prerequisite satisfied (forced): x = xrandom(0)'))

        # force satisfy it again
        schd.xtrigger_mgr.force_satisfy(foo, xtrigs)
        assert foo.state.xtriggers['x']  # satisified
        assert log_filter(
            contains=(
                'xtrigger prerequisite already satisfied: x = xrandom(0)'))

        # force unsatisfy it
        schd.xtrigger_mgr.force_satisfy(foo, {"x": False})
        assert not foo.state.xtriggers['x']  # not satisified
        assert log_filter(
            contains=(
                'xtrigger prerequisite unsatisfied (forced): x = xrandom(0)'))

        # force unsatisfy it again
        schd.xtrigger_mgr.force_satisfy(foo, {"x": False})
        assert not foo.state.xtriggers['x']  # not satisified
        assert log_filter(contains=(
            'xtrigger prerequisite already unsatisfied: x = xrandom(0)'
        ))

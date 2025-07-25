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
"""Test that using [runtime][TASK]run mode works in each mode.

Point 3 of the Skip Mode proposal
https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md

| The run mode should be controlled by a new task configuration
| [runtime][<namespace>]run mode with the default being live.
| As a runtime configuration, this can be defined in the workflow
| for development / testing purposes or set by cylc broadcast.

n.b: This is pretty much a functional test and
probably ought to be labelled as such, but uses the
integration test framework.
"""

import pytest

from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.run_modes import WORKFLOW_RUN_MODES, RunMode
from cylc.flow.scheduler import Scheduler, SchedulerStop
from cylc.flow.task_state import TASK_STATUS_WAITING
from cylc.flow.commands import (
    run_cmd,
    force_trigger_tasks
)


@pytest.mark.parametrize('workflow_run_mode', sorted(WORKFLOW_RUN_MODES))
async def test_run_mode_override_from_config(
    capture_live_submissions,
    flow,
    scheduler,
    run,
    complete,
    workflow_run_mode,
    validate
):
    """Test that `[runtime][<namespace>]run mode` overrides workflow modes."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'live & skip',
            },
        },
        'runtime': {
            'live': {'run mode': 'live'},
            'skip': {'run mode': 'skip'},
        }
    })
    run_mode = RunMode(workflow_run_mode)
    validate(id_)
    schd = scheduler(id_, run_mode=run_mode, paused_start=False)
    async with run(schd):
        await complete(schd)

    if workflow_run_mode == 'live':
        assert capture_live_submissions() == {'1/live'}
    elif workflow_run_mode == 'dummy':
        # Skip mode doesn't override dummy mode:
        assert capture_live_submissions() == {'1/live', '1/skip'}
    else:
        assert capture_live_submissions() == set()


async def test_force_trigger_does_not_override_run_mode(
    flow,
    scheduler,
    start,
):
    """Force-triggering a task will not override the run mode.

    Taken from spec at
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md#proposal
    """
    wid = flow({
        'scheduling': {'graph': {'R1': 'foo'}},
        'runtime': {'foo': {'run mode': 'skip'}}
    })
    schd = scheduler(wid, run_mode="live")
    async with start(schd):
        foo = schd.pool.get_tasks()[0]

        # Force trigger task:
        run_cmd(force_trigger_tasks(schd, '1/foo', [1]))

        # ... but job submission will always change this to the correct mode:
        schd.submit_task_jobs([foo])

        assert foo.run_mode.value == 'skip'


async def test_run_mode_skip_abides_by_held(flow, scheduler, run):
    """Tasks with run mode = skip will continue to abide by the
    is_held flag as normal.

    Taken from spec at
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md#proposal
    """
    wid = flow({
        'scheduling': {'graph': {'R1': 'foo'}},
        'runtime': {'foo': {'run mode': 'skip'}}
    })
    schd: Scheduler = scheduler(wid, run_mode="live", paused_start=False)
    async with run(schd):
        foo = schd.pool.get_tasks()[0]
        assert not foo.state.is_held

        # Hold task, check that it's held:
        schd.pool.hold_tasks(['1/foo'])
        assert foo.state.is_held
        await schd._main_loop()
        assert foo.state(TASK_STATUS_WAITING)

        schd.pool.release_held_tasks(['1/foo'])
        assert not foo.state.is_held
        with pytest.raises(SchedulerStop):
            # Will shut down as foo has run
            await schd._main_loop()


async def test_run_mode_override_from_broadcast(
    flow, scheduler, start, complete, log_filter, capture_live_submissions
):
    """Test that run_mode modifications only apply to one task.
    """
    cfg = {
        "scheduler": {"cycle point format": "%Y"},
        "scheduling": {
            "initial cycle point": "1000",
            "final cycle point": "1001",
            "graph": {"P1Y": "foo"}},
        "runtime": {
        }
    }
    id_ = flow(cfg)
    schd = scheduler(id_, run_mode='live', paused_start=False)

    async with start(schd):
        schd.broadcast_mgr.put_broadcast(
            ['1000'], ['foo'], [{'run mode': 'skip'}])

        foo_1000 = schd.pool.get_task(ISO8601Point('1000'), 'foo')
        foo_1001 = schd.pool.get_task(ISO8601Point('1001'), 'foo')

        schd.submit_task_jobs([foo_1000, foo_1001])
        assert foo_1000.run_mode.value == 'skip'
        assert capture_live_submissions() == {'1001/foo'}

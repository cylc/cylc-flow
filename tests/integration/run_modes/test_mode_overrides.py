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


@pytest.mark.parametrize(
    'workflow_run_mode', [('live'), ('skip')])
async def test_run_mode_override_from_config(
    workflow_run_mode, flow, scheduler, run, complete, log_filter
):
    """Test that ``[runtime][TASK]run mode`` overrides workflow modes.
    """
    cfg = {
        "scheduler": {"cycle point format": "%Y"},
        "scheduling": {
            "initial cycle point": "1000",
            "final cycle point": "1000",
            "graph": {"P1Y": "live_\nskip_\ndefault_"}},
        "runtime": {
            "skip_": {"run mode": "skip"},
            "live_": {"run mode": "live"}
        }
    }
    id_ = flow(cfg)
    schd = scheduler(id_, run_mode=workflow_run_mode, paused_start=False)
    expect_template = (
        '[1000/{}_/01:preparing] submitted to localhost:background')

    async with run(schd) as log:
        await complete(schd)

        # Live task has been really submitted:
        assert log_filter(log, contains=expect_template.format('live'))

        # Default is the same as workflow:
        if workflow_run_mode == 'live':
            assert log_filter(log, contains=expect_template.format('default'))
        else:
            assert log_filter(
                log, contains='[1000/default_/01:running] => succeeded')
            assert not log_filter(
                log, contains=expect_template.format('default'))

        # Skip task has run, but not actually been submitted:
        assert log_filter(log, contains='[1000/skip_/01:running] => succeeded')
        assert not log_filter(log, contains=expect_template.format('skip'))


async def test_force_trigger_does_not_override_run_mode(
    flow,
    scheduler,
    start,
):
    """Force-triggering a task will not override the run mode.

    Tasks with run mode = skip will continue to abide by
    the is_held flag as normal.

    Taken from spec at
    https://github.com/cylc/cylc-admin/blob/master/
        docs/proposal-skip-mode.md#proposal
    """
    wid = flow({
        'scheduling': {'graph': {'R1': 'foo'}},
        'runtime': {'foo': {'run mode': 'skip'}}
    })
    schd = scheduler(wid)
    async with start(schd):
        # Check that task isn't held at first
        foo = schd.pool.get_tasks()[0]
        assert foo.state.is_held is False

        # Hold task, check that it's held:
        schd.pool.hold_tasks('1/foo')
        assert foo.state.is_held is True

        # Trigger task, check that it's _still_ held:
        schd.pool.force_trigger_tasks('1/foo', [1])
        assert foo.state.is_held is True

        # run_mode will always be simulation from test
        # workflow before submit routine...
        assert not foo.run_mode

        # ... but job submission will always change this to the correct mode:
        schd.task_job_mgr.submit_task_jobs(
            schd.workflow,
            [foo],
            schd.server.curve_auth,
            schd.server.client_pub_key_dir)
        assert foo.run_mode == 'skip'


async def test_run_mode_override_from_broadcast(
    flow, scheduler, run, complete, log_filter
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

    async with run(schd):
        schd.broadcast_mgr.put_broadcast(
            ['1000'], ['foo'], [{'run mode': 'skip'}])

        foo_1000, foo_1001 = schd.pool.get_tasks()

        schd.task_job_mgr.submit_task_jobs(
            schd.workflow,
            [foo_1000, foo_1001],
            schd.server.curve_auth,
            schd.server.client_pub_key_dir)

        assert foo_1000.run_mode == 'skip'
        assert foo_1001.run_mode == 'live'

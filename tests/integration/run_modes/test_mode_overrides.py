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

TODO: This is pretty much a functional test and
probably ought to be labelled as such, but uses the
integration test framework.
"""

import pytest


@pytest.mark.parametrize(
    'workflow_run_mode', [('live'), ('simulation'), ('dummy')])   #, ('skip')])
async def test_run_mode_override(
    workflow_run_mode, flow, scheduler, run, complete, log_filter
):
    """Test that ``[runtime][TASK]run mode`` overrides workflow modes.

    Can only be run for tasks which run in ghost modes.
    """
    default_ = (
        '\ndefault_' if workflow_run_mode in ['simulation', 'skip'] else '')

    cfg = {
        "scheduler": {"cycle point format": "%Y"},
        "scheduling": {
            "initial cycle point": "1000",
            "final cycle point": "1000",
            "graph": {"P1Y": f"sim_\nskip_{default_}"}},
        "runtime": {
            "sim_": {
                "run mode": "simulation",
                'simulation': {'default run length': 'PT0S'}
            },
            "skip_": {"run mode": "skip"},
        }
    }
    id_ = flow(cfg)
    schd = scheduler(id_, run_mode=workflow_run_mode, paused_start=False)
    expect = ('[1000/sim_] run mode set by task settings to: simulation mode.')

    async with run(schd) as log:
        await complete(schd)
        if workflow_run_mode == 'simulation':
            # No message in simulation mode.
            assert not log_filter(log, contains=expect)
        else:
            assert log_filter(log, contains=expect)


@pytest.mark.parametrize('mode', (('skip'), ('simulation'), ('dummy')))
async def test_force_trigger_does_not_override_run_mode(
    flow,
    scheduler,
    start,
    mode,
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
        'runtime': {'foo': {'run mode': mode}}
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
        assert foo.tdef.run_mode == 'simulation'

        # ... but job submission will always change this to the correct mode:
        schd.task_job_mgr.submit_task_jobs(
            schd.workflow,
            [foo],
            schd.server.curve_auth,
            schd.server.client_pub_key_dir)
        assert foo.tdef.run_mode == mode

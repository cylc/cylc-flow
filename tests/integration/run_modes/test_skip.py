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
"""Test for skip mode integration.
"""

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.id import TaskTokens
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_outputs import TASK_OUTPUT_FAILED
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED,
)


async def test_settings_override_from_broadcast(
    flow, scheduler, start, complete, log_filter
):
    """Test that skip mode runs differently if settings are modified.
    """
    cfg = {
        "scheduling": {"graph": {"R1": "foo:failed => bar"}},
        "runtime": {
            "foo": {
                "events": {
                    'handler events': 'failed',
                    "handlers": 'echo "HELLO"'
                }
            }
        }
    }
    id_ = flow(cfg)
    schd = scheduler(id_, run_mode='live')

    async with start(schd):
        schd.broadcast_mgr.put_broadcast(
            ['1'],
            ['foo'],
            [
                {'run mode': 'skip'},
                {'skip': {'outputs': 'failed'}},
                {'skip': {'disable task event handlers': "False"}}
            ]
        )

        foo, = schd.pool.get_tasks()

        schd.submit_task_jobs(schd.pool.get_tasks())
        # Run mode has changed:
        assert foo.platform['name'] == 'skip'
        # Output failed emitted:
        assert foo.state.status == 'failed'
        # After processing events there is a handler in the subprocpool:
        schd.task_events_mgr.process_events(schd)
        assert 'echo "HELLO"' in schd.proc_pool.is_not_done()[0][0].cmd


async def test_broadcast_changes_set_skip_outputs(
    flow, scheduler, start
):
    """When cylc set --out skip is used, task outputs are updated with
    broadcasts.

    Skip mode proposal point 4
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md

    | The cylc set --out option should accept the skip value which should
    | set the outputs defined in [runtime][<namespace>][skip]outputs.
    | The skip keyword should not be allowed in custom outputs.
    """
    wid = flow({
        'scheduling': {'graph': {'R1': 'foo:x?\nfoo:y?'}},
        'runtime': {'foo': {'outputs': {
            'x': 'some message', 'y': 'another message'}}}
    })
    schd = scheduler(wid, run_mode='live')
    async with start(schd):
        schd.broadcast_mgr.put_broadcast(
            ['1'],
            ['foo'],
            [{'skip': {'outputs': 'x'}}],
        )
        foo, = schd.pool.get_tasks()
        schd.pool.set_prereqs_and_outputs(
            {TaskTokens('1', 'foo')}, ['skip'], [], [])

        foo_outputs = foo.state.outputs.get_completed_outputs()

        assert foo_outputs == {
            'submitted': '(manually completed)',
            'started': '(manually completed)',
            'succeeded': '(manually completed)',
            'x': '(manually completed)'}


async def test_skip_mode_outputs(
    flow, scheduler, reftest,
):
    """Skip mode can be configured by the `[runtime][<namespace>][skip]`
    section.

    Skip mode proposal point 2
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md
    """
    graph = r"""
        # By default, all required outputs will be generated
        # plus succeeded if success is optional:
        foo? & foo:required_out => success_if_optional & required_outs

        # The outputs submitted and started are always produced
        # and do not need to be defined in [runtime][X][skip]outputs:
        foo:submitted => submitted_always
        foo:started => started_always

        # If outputs is specified and does not include either
        # succeeded or failed then succeeded will be produced.
        opt:optional_out? => optional_outs_produced

        should_fail:fail => did_fail
    """
    wid = flow({
        'scheduling': {'graph': {'R1': graph}},
        'runtime': {
            'root': {
                'run mode': 'skip',
                'outputs': {
                    'required_out': 'the plans have been on display...',
                    'optional_out': 'its only four light years away...'
                }
            },
            'opt': {
                'skip': {
                    'outputs': 'optional_out'
                }
            },
            'should_fail': {
                'skip': {
                    'outputs': 'failed'
                }
            }
        }
    })
    schd = scheduler(wid, run_mode='live', paused_start=False)
    assert await reftest(schd) == {
        ('1/did_fail', ('1/should_fail',),),
        ('1/foo', None,),
        ('1/opt', None,),
        ('1/optional_outs_produced', ('1/opt',),),
        ('1/required_outs', ('1/foo', '1/foo',),),
        ('1/should_fail', None,),
        ('1/started_always', ('1/foo',),),
        ('1/submitted_always', ('1/foo',),),
        ('1/success_if_optional', ('1/foo', '1/foo',),),
    }


async def test_doesnt_release_held_tasks(
    one_conf, flow, scheduler, start, log_filter, capture_live_submissions
):
    """Point 5 of the proposal
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md

    | Tasks with run mode = skip will continue to abide by the is_held
    | flag as normal.

    """
    one_conf['runtime'] = {'one': {'run mode': 'skip'}}
    schd = scheduler(flow(one_conf), run_mode='live', paused_start=False)
    async with start(schd):
        msg = 'held tasks shoudn\'t {}'

        # Set task to held and check submission in skip mode doesn't happen:
        schd.pool.hold_tasks({TaskTokens('1', 'one')})
        schd.release_tasks_to_run()

        assert not log_filter(contains='=> running'), msg.format('run')
        assert not log_filter(contains='=> succeeded'), msg.format('succeed')

        # Release held task and assert that it now skips successfully:
        schd.pool.release_held_tasks({TaskTokens('1', 'one')})
        schd.release_tasks_to_run()

        assert log_filter(contains='=> running'), msg.format('run')
        assert log_filter(contains='=> succeeded'), msg.format('succeed')


async def test_prereqs_marked_satisfied_by_skip_mode(
    flow, scheduler, start, log_filter, complete
):
    """Point 8 from the skip mode proposal
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md

    | When tasks are run in skip mode, the prerequisites which correspond
    | to the outputs they generate should be marked as "satisfied by skip mode"
    | rather than "satisfied naturally" for provenance reasons.
    """
    schd = scheduler(flow({
        'scheduling': {'graph': {'R1': 'foo => bar'}},
        'runtime': {'foo': {'run mode': 'skip'}}
    }), run_mode='live')

    async with start(schd):
        foo = schd.pool.get_task(IntegerPoint(1), 'foo')
        schd.submit_task_jobs([foo])
        bar = schd.pool.get_task(IntegerPoint(1), 'bar')
        satisfied_message, = bar.state.prerequisites[0]._satisfied.values()
        assert satisfied_message == 'satisfied by skip mode'


async def test_outputs_can_be_changed(
    one_conf, flow, start, scheduler, validate
):
    schd = scheduler(flow(one_conf), run_mode='live')
    async with start(schd):
        # Broadcast the task into skip mode, output failed and submit it:
        schd.broadcast_mgr.put_broadcast(
            ["1"],
            ["one"],
            [
                {"run mode": "skip"},
                {"skip": {"outputs": "failed"}},
            ],
        )
        schd.submit_task_jobs(schd.pool.get_tasks())

        # Broadcast the task into skip mode, output succeeded and submit it:
        schd.broadcast_mgr.put_broadcast(
            ['1'], ['one'], [{'skip': {'outputs': 'succeeded'}}]
        )
        schd.submit_task_jobs(schd.pool.get_tasks())


async def test_rerun_after_skip_mode_broadcast(
    flow, one_conf, scheduler, start
):
    """Test re-running a task after it has been set to skip.

    See https://github.com/cylc/cylc-flow/pull/6940
    """
    id_ = flow({
        **one_conf,
        "runtime": {
            "one": {
                "execution time limit": "PT1M",
            },
        },
    })
    schd: Scheduler = scheduler(id_, run_mode='live')
    async with start(schd):
        itask = schd.pool.get_tasks()[0]
        schd.submit_task_jobs([itask])
        schd.task_events_mgr.process_message(
            itask, 'CRITICAL', TASK_OUTPUT_FAILED
        )
        assert itask.state(TASK_STATUS_FAILED)

        schd.broadcast_mgr.put_broadcast(
            ['1'], ['root'], [{'run mode': 'skip'}]
        )
        schd.submit_task_jobs([itask])
        assert itask.state(TASK_STATUS_SUCCEEDED)

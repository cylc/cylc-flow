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

        schd.task_job_mgr.submit_task_jobs(
            schd.workflow,
            schd.pool.get_tasks(),
            schd.server.curve_auth,
            schd.server.client_pub_key_dir
        )
        # Run mode has changed:
        assert foo.platform['name'] == 'skip'
        # Output failed emitted:
        assert foo.state.status == 'failed'
        # After processing events there is a handler in the subprocpool:
        schd.task_events_mgr.process_events(schd)
        assert 'echo "HELLO"' in schd.proc_pool.is_not_done()[0][0].cmd


async def test_broadcast_changes_set_skip_outputs(
    flow, scheduler, start, complete, log_filter
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
        'scheduling': {'graph': {'R1': 'foo:expect_this'}},
        'runtime': {'foo': {'outputs': {'expect_this': 'some message'}}}
    })
    schd = scheduler(wid, run_mode='live')
    async with start(schd):
        schd.broadcast_mgr.put_broadcast(
            ['1'],
            ['foo'],
            [{'skip': {'outputs': 'expect_this'}}],
        )
        foo, = schd.pool.get_tasks()
        schd.pool.set_prereqs_and_outputs(
            '1/foo', ['skip'], [], ['all'])

        foo_outputs = foo.state.outputs.get_completed_outputs()

        assert 'expect_this' in foo_outputs
        assert foo_outputs['expect_this'] == '(manually completed)'


async def test_skip_mode_outputs(
    flow, scheduler, reftest,
):
    """Nearly a functional test of the output emission of skip mode tasks

    Skip mode proposal point 2
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md
    """
    graph = """
        # By default, all required outputs will be generated
        # plus succeeded if success is optional:
        foo? & foo:required_out => success_if_optional & required_outs
        
        # The outputs submitted and started are always produced
        # and do not need to be defined in outputs:
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
    one_conf, flow, scheduler, start, log_filter
):
    """Point 5 of the proposal
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md

    | Tasks with run mode = skip will continue to abide by the is_held
    | flag as normal.

    """
    schd = scheduler(flow(one_conf), run_mode='skip')
    async with start(schd) as log:
        itask = schd.pool.get_tasks()[0]
        msg = 'held tasks shoudn\'t {}'

        # Set task to held and check submission in skip mode doesn't happen:
        itask.state.is_held = True
        schd.task_job_mgr.submit_task_jobs(
            schd.workflow,
            [itask],
            schd.server.curve_auth,
            schd.server.client_pub_key_dir,
            run_mode=schd.get_run_mode()
        )
        assert not log_filter(log, contains='=> running'), msg.format('run')
        assert not log_filter(log, contains='=> succeeded'), msg.format(
            'succeed')

        # Release held task and assert that it now skips successfully:
        schd.pool.release_held_tasks(['1/one'])
        schd.task_job_mgr.submit_task_jobs(
            schd.workflow,
            [itask],
            schd.server.curve_auth,
            schd.server.client_pub_key_dir,
            run_mode=schd.get_run_mode()
        )
        assert log_filter(log, contains='=> running'), msg.format('run')
        assert log_filter(log, contains='=> succeeded'), msg.format('succeed')


async def test_force_trigger_doesnt_change_mode(
    flow, scheduler, run, complete
):
    """Point 6 from the skip mode proposal
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-skip-mode.md

    | Force-triggering a task will not override the run mode.
    """
    wid = flow({
        'scheduling': {'graph': {'R1': 'slow => skip'}},
        'runtime': {
            'slow': {'script': 'sleep 6'},
            'skip': {'script': 'exit 1', 'run mode': 'skip'}
        }
    })
    schd = scheduler(wid, run_mode='live', paused_start=False)
    async with run(schd):
        schd.pool.force_trigger_tasks(['1/skip'], [1])
        # This will timeout if the skip task has become live on triggering:
        await complete(schd, '1/skip', timeout=6)


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
        'scheduling': {'graph': {'R1': 'foo => bar'}}
    }), run_mode='skip')

    async with start(schd) as log:
        foo, = schd.pool.get_tasks()
        schd.task_job_mgr.submit_task_jobs(
            schd.workflow,
            [foo],
            schd.server.curve_auth,
            schd.server.client_pub_key_dir,
            run_mode=schd.get_run_mode()
        )
        bar, = schd.pool.get_tasks()
        satisfied_message, = bar.state.prerequisites[0]._satisfied.values()
        assert satisfied_message == 'satisfied by skip mode'

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

"""Tests for reload behaviour in the scheduler."""


from cylc.flow import (
    commands,
    flags,
)
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.data_store_mgr import TASK_PROXIES
from cylc.flow.platforms import get_platform
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_state import (
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_WAITING,
)


async def test_reload_waits_for_pending_tasks(
    flow,
    scheduler,
    start,
    monkeypatch,
    log_scan,
):
    """Reload should flush out preparing tasks and pause the workflow.

    Reloading a workflow with preparing tasks may be unsafe and is at least
    confusing. For safety we should pause the workflow and flush out any
    preparing tasks before attempting reload.

    See https://github.com/cylc/cylc-flow/issues/5107
    """
    # speed up the test:
    monkeypatch.setattr('cylc.flow.scheduler.sleep', lambda *_: None)
    # a simple workflow with a single task
    id_ = flow('foo')
    schd: Scheduler = scheduler(id_, paused_start=False)

    # we will artificially push the task through these states
    state_seq = [
        # repeat the preparing state a few times to simulate a task
        # taking multiple main-loop cycles to submit
        TASK_STATUS_PREPARING,
        TASK_STATUS_PREPARING,
        TASK_STATUS_PREPARING,
        TASK_STATUS_SUBMITTED,
    ]

    # start the scheduler
    async with start(schd) as log:
        foo = schd.pool.get_tasks()[0]

        # set the task to go through some state changes
        def submit_task_jobs(*a, **k):
            try:
                foo.state_reset(state_seq.pop(0))
            except IndexError:
                foo.waiting_on_job_prep = False
            return [foo]

        monkeypatch.setattr(
            schd.task_job_mgr, 'submit_task_jobs', submit_task_jobs
        )

        # the task should start as waiting
        assert foo.state(TASK_STATUS_WAITING)

        # put the task into the preparing state
        schd.release_tasks_to_run()
        assert foo.state(TASK_STATUS_PREPARING)

        # reload the workflow
        await commands.run_cmd(commands.reload_workflow(schd))

        # the task should end in the submitted state
        assert foo.state(TASK_STATUS_SUBMITTED)

        # ensure the order of events was correct
        log_scan(
            log,
            [
                # the task should have entered the preparing state before the
                # reload was requested
                '[1/foo:waiting] => preparing',
                # the reload should have put the workflow into the paused state
                'Pausing the workflow: Reloading workflow',
                # reload should have waited for the task to submit
                '[1/foo/00:preparing] => submitted',
                # before then reloading the workflow config
                'Reloading the workflow definition.',
                # post-reload the workflow should have been resumed
                'RESUMING the workflow now',
            ],
        )


async def test_reload_failure(
    flow,
    one_conf,
    scheduler,
    start,
    log_filter,
):
    """Reload should not crash the workflow on config errors.

    A warning should be logged along with the error.
    """
    id_ = flow(one_conf)
    schd = scheduler(id_)
    async with start(schd):
        # corrupt the config by removing the scheduling section
        two_conf = {**one_conf, 'scheduling': {}}
        flow(two_conf, workflow_id=id_)

        # reload the workflow
        await commands.run_cmd(commands.reload_workflow(schd))

        # the reload should have failed but the workflow should still be
        # running
        assert log_filter(
            contains=(
                'Reload failed - WorkflowConfigError:'
                ' missing [scheduling][[graph]] section'
            )
        )

        # the config should be unchanged
        assert schd.config.cfg['scheduling']['graph']['R1'] == 'one'


async def test_reload_global_platform(
    flow,
    one_conf,
    scheduler,
    start,
    log_filter,
    tmp_path,
    monkeypatch,
):
    global_config_path = tmp_path / 'global.cylc'
    monkeypatch.setenv("CYLC_CONF_PATH", str(global_config_path.parent))

    # Original global config file
    global_config_path.write_text("""
    [platforms]
        [[localhost]]
            [[[meta]]]
                x = 1
    """)
    glbl_cfg(reload=True)
    assert glbl_cfg().get(['platforms', 'localhost', 'meta', 'x']) == '1'

    id_ = flow(one_conf)
    schd = scheduler(id_)
    async with start(schd):
        # Task platforms reflect the original config
        rtconf = schd.broadcast_mgr.get_updated_rtconfig(
            schd.pool.get_tasks()[0]
        )
        platform = get_platform(rtconf)
        assert platform['meta']['x'] == '1'

        # Modify the global config file
        global_config_path.write_text("""
        [platforms]
            [[localhost]]
                [[[meta]]]
                    x = 2
        """)

        # reload the workflow and global config
        await commands.run_cmd(
            commands.reload_workflow(schd, reload_global=True)
        )

        # Global config should have been reloaded
        assert log_filter(contains=('Reloading the global configuration.'))

        # Task platforms reflect the new config
        rtconf = schd.broadcast_mgr.get_updated_rtconfig(
            schd.pool.get_tasks()[0]
        )
        platform = get_platform(rtconf)
        assert platform['meta']['x'] == '2'

        # Modify the global config file with an error
        global_config_path.write_text("""
        [ERROR]
        [platforms]
            [[localhost]]
                [[[meta]]]
                    x = 3
        """)

        # reload the workflow and global config
        await commands.run_cmd(
            commands.reload_workflow(schd, reload_global=True)
        )

        # Error is noted in the log
        assert log_filter(
            contains=(
                'This is probably due to an issue with the new configuration.'
            )
        )

        # Task platforms should be the last valid value
        rtconf = schd.broadcast_mgr.get_updated_rtconfig(
            schd.pool.get_tasks()[0]
        )
        platform = get_platform(rtconf)
        assert platform['meta']['x'] == '2'

        # reload the workflow in verbose mode
        flags.verbosity = 2
        await commands.run_cmd(
            commands.reload_workflow(schd, reload_global=True)
        )

        # Traceback is shown in the log
        # (match for ERROR, trace is not captured)
        assert log_filter(exact_match='ERROR')


async def test_reload_global_platform_group(
    flow,
    scheduler,
    start,
    log_filter,
    tmp_path,
    monkeypatch,
):
    global_config_path = tmp_path / 'global.cylc'
    monkeypatch.setenv("CYLC_CONF_PATH", str(global_config_path.parent))

    # Original global config file
    global_config_path.write_text("""
    [platforms]
        [[foo]]
            [[[meta]]]
                x = 1
    [platform groups]
        [[pg]]
            platforms = foo
    """)
    glbl_cfg(reload=True)

    # Task using the platform group
    conf = {
        'scheduling': {'graph': {'R1': 'one'}},
        'runtime': {
            'one': {
                'platform': 'pg',
            }
        },
    }

    id_ = flow(conf)
    schd = scheduler(id_)
    async with start(schd):
        # Task platforms reflect the original config
        rtconf = schd.broadcast_mgr.get_updated_rtconfig(
            schd.pool.get_tasks()[0]
        )
        platform = get_platform(rtconf)
        assert platform['meta']['x'] == '1'

        # Modify the global config file
        global_config_path.write_text("""
        [platforms]
            [[bar]]
                [[[meta]]]
                    x = 2
        [platform groups]
            [[pg]]
                platforms = bar
        """)

        # reload the workflow and global config
        await commands.run_cmd(
            commands.reload_workflow(schd, reload_global=True)
        )

        # Global config should have been reloaded
        assert log_filter(contains=('Reloading the global configuration.'))

        # Task platforms reflect the new config
        rtconf = schd.broadcast_mgr.get_updated_rtconfig(
            schd.pool.get_tasks()[0]
        )
        platform = get_platform(rtconf)
        assert platform['meta']['x'] == '2'


async def test_orphan_reload(
    flow,
    scheduler,
    start,
    log_filter,
):
    """Reload should not fail because of orphaned tasks.

    The following aspects of reload-with-orphans are tested:
        - Broadcast deltas generated after reload.
          https://github.com/cylc/cylc-flow/issues/6814
        - Removal of both xtrigger and associated active/incomplete task.
          https://github.com/cylc/cylc-flow/issues/6815

    (Orphans being active/incomplete tasks removed from reloaded workflow cfg.)
    """
    before = {
        'scheduling': {
            'initial cycle point': '20010101T0000Z',
            'graph': {
                'R1': '''
                    foo => bar
                    @wall_clock => bar
                '''
            }
        }
    }
    after = {
        'scheduling': {
            'initial cycle point': '20010101T0000Z',
            'graph': {
                'R1': 'foo'
            }
        }
    }
    id_ = flow(before)
    schd = scheduler(id_)
    async with start(schd):
        # spawn in bar
        foo = schd.pool._get_task_by_id('20010101T0000Z/foo')
        schd.pool.task_events_mgr.process_message(foo, 'INFO', 'succeeded')
        bar = schd.pool._get_task_by_id('20010101T0000Z/bar')
        # set bar to failed
        schd.pool.task_events_mgr.process_message(bar, 'INFO', 'failed')

        # Save our progress
        schd.workflow_db_mgr.put_task_pool(schd.pool)

        # Change workflow to one without bar and xtrigger
        flow(after, workflow_id=id_)

        # reload the workflow
        await commands.run_cmd(commands.reload_workflow(schd))

        # test broadcast delta over orphaned task
        schd.data_store_mgr.delta_broadcast()

        # the reload should have completed successfully
        assert log_filter(
            contains=('Reload completed')
        )


async def test_data_store_tproxy(flow, scheduler, start):
    """Check N>0 task proxy in data store has correct info on reload.

    https://github.com/cylc/cylc-flow/issues/6973
    """
    schd: Scheduler = scheduler(flow('foo => bar'))

    def get_ds_tproxy(task):
        return schd.data_store_mgr.data[schd.id][TASK_PROXIES][
            f'{schd.id}//1/{task}'
        ]

    async with start(schd):
        await schd.update_data_structure()
        assert str(get_ds_tproxy('bar').runtime)

        await commands.run_cmd(commands.reload_workflow(schd))
        assert str(get_ds_tproxy('bar').runtime)

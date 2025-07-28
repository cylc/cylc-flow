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

import logging
from typing import (
    Any as Fixture,
    Callable
)

import pytest

from cylc.flow.commands import (
    force_trigger_tasks,
    reload_workflow,
    hold,
    resume,
    run_cmd,
    set_prereqs_and_outputs,
)
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.task_state import TASK_STATUS_WAITING


async def test_trigger_workflow_paused(
    flow: 'Fixture',
    scheduler: 'Fixture',
    start: 'Fixture',
    capture_submission: 'Fixture',
    log_filter: Callable
):
    """
    Test manual triggering when the workflow is paused.

    The usual queue limiting behaviour is expected.

    https://github.com/cylc/cylc-flow/issues/6192

    """
    id_ = flow({
        'scheduling': {
            'queues': {
                'default': {
                    'limit': 1,
                },
            },
            'graph': {
                'R1': '''
                    a => x & y & z
                ''',
            },
        },
    })
    schd = scheduler(id_, paused_start=True)

    # start the scheduler (but don't set the main loop running)
    async with start(schd):

        # capture task submissions (prevents real submissions)
        submitted_tasks = capture_submission(schd)

        # paused at start-up so no tasks should be submitted
        assert len(submitted_tasks) == 0

        # manually trigger 1/x - it should be submitted
        await run_cmd(force_trigger_tasks(schd, ['1/x'], ["1"]))
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 1

        # manually trigger 1/y - it should be queued but not submitted
        # (queue limit reached)
        await run_cmd(force_trigger_tasks(schd, ['1/y'], ["1"]))
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 1

        # manually trigger 1/y again - it should be submitted
        # (triggering a queued task runs it)
        await run_cmd(force_trigger_tasks(schd, ['1/y'], ["1"]))
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 2

        # manually trigger 1/y yet again - the trigger should be ignored
        # (task already active)
        await run_cmd(force_trigger_tasks(schd, ['1/y'], ["1"]))
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 2
        assert log_filter(
            level=logging.WARNING,
            contains="Job already in process - ignoring"
        )


async def test_trigger_group_whilst_paused(flow, scheduler, run, complete):
    """Only group start tasks should run whilst the scheduler is paused.

    Group start tasks have only off-group dependencies.

    Others (with in-group dependencies) should run as normal when their
    prerequisites are satisfied once the workflow is resumed.

    """
    id_ = flow(
        {
            'scheduling': {
                'graph': {'R1': 'a => b => c => d'},
            },
        }
    )
    schd = scheduler(id_)
    async with run(schd):
        # trigger the chain
        await run_cmd(force_trigger_tasks(schd, ['1/a'], []))

        # 1/a should run whilst the workflow is paused (group start-task)
        await complete(schd, '1/a', allow_paused=True, timeout=1)

        # 1/b should *not* run whilst the workflow is paused
        with pytest.raises(AssertionError):
            await complete(schd, '1/b', allow_paused=True, timeout=2)

        b = schd.pool._get_task_by_id('1/b')
        assert b.state.status == TASK_STATUS_WAITING

        # 1/b and 1/c should run once the workflow is resumed
        await run_cmd(resume(schd))
        await complete(schd, '1/c')


async def test_trigger_on_resume(
    flow: 'Fixture',
    scheduler: 'Fixture',
    start: 'Fixture',
    capture_submission: 'Fixture',
):
    """
    Test manual triggering on-resume option when the workflow is paused.

    https://github.com/cylc/cylc-flow/issues/6192

    """
    id_ = flow({
        'scheduling': {
            'queues': {
                'default': {
                    'limit': 1,
                },
            },
            'graph': {
                'R1': '''
                    a => x & y & z
                ''',
            },
        },
    })
    schd = scheduler(id_, paused_start=True)

    # start the scheduler (but don't set the main loop running)
    async with start(schd):

        # capture task submissions (prevents real submissions)
        submitted_tasks = capture_submission(schd)

        # paused at start-up so no tasks should be submitted
        assert len(submitted_tasks) == 0

        # manually trigger 1/x - it not should be submitted
        await run_cmd(
            force_trigger_tasks(schd, ['1/x'], ["1"], on_resume=True))
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 0

        # manually trigger 1/y - it should not be submitted
        # (queue limit reached)
        await run_cmd(
            force_trigger_tasks(schd, ['1/y'], ["1"], on_resume=True))
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 0

        # manually trigger 1/y again - it should not be submitted
        # (triggering a queued task runs it)
        await run_cmd(
            force_trigger_tasks(schd, ['1/y'], ["1"], on_resume=True))
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 0

        # resume the workflow, both tasks should trigger now.
        schd.resume_workflow()
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 2


async def test_trigger_group(
    flow, scheduler, run, complete, log_filter
):
    """Test trigger of a sub-graph of future, then past, tasks.

    It should satisfy off-group task and xtrigger prerequisites automatically.

    """
    cfg = {
        'scheduling': {
            'xtriggers': {
                'xr': 'xrandom(0)'  # never satisfied
            },
            'special tasks': {
                'external-trigger': 'xt(cheese)'
            },
            'graph': {
                'R1': """
                    # upstream:
                    x => a

                    # sub-graph for group trigger:
                    a => b & c & xt => d

                    # downstream:
                    d => e => y

                    # off-group prerequisites:
                    @xr => x  # stop the flow starting
                    @xr => c  # off-group xtrigger prerequisite
                    @xr => off => b  # off-group task prerequisite
                    # (plus task xt has a push external trigger)

                    # stop the flow from ending without intervention:
                    @xr => y
                """
            },
        },
    }
    id_ = flow(cfg)
    schd = scheduler(id_, paused_start=False)
    async with run(schd, level=logging.INFO) as log:
        # Trigger the group ahead of the flow.
        # It should run the group and flow on to downstream task e.
        await run_cmd(
            force_trigger_tasks(schd, ['1/a', '1/b', '1/c', '1/d', '1/xt'], [])
        )
        await complete(schd, '1/e')

        # It should satisfy off-group prerequisites.
        assert log_filter(
            regex="1/c:waiting.*prerequisite force-satisfied: xr = xrandom")
        assert log_filter(
            regex="1/b:waiting.*prerequisite force-satisfied: 1/off:succeeded")
        assert log_filter(
            regex="1/a:waiting.*prerequisite force-satisfied: 1/x:succeeded")
        assert log_filter(
            regex='1/xt:waiting.*external trigger force-satisfied: "cheese"')

        log.clear()

        # Trigger the group again, now as past tasks, in the same flow.
        # It should erase flow 1 history to allow the rerun.
        # It should not flow on to e, which already ran in flow 1.

        # Create an active task that needs removing, to test that.
        await run_cmd(
            set_prereqs_and_outputs(schd, ['1/c'], [], [], ['all'])
        )
        await run_cmd(
            force_trigger_tasks(schd, ['1/a', '1/b', '1/c', '1/d', '1/xt'], [])
        )
        await complete(schd, '1/d')

        assert log_filter(
            contains=(
                "Removed tasks: 1/a (flows=1), 1/b (flows=1),"
                " 1/c (flows=1), 1/d (flows=1), 1/xt (flows=1)"
            )
        )
        assert log_filter(
            regex="1/c:waiting.*prerequisite force-satisfied: xr = xrandom")
        assert log_filter(
            regex="1/b:waiting.*prerequisite force-satisfied: 1/off:succeeded")
        assert log_filter(
            regex="1/a:waiting.*prerequisite force-satisfied: 1/x:succeeded")
        assert log_filter(
            regex='1/xt:waiting.*external trigger force-satisfied: "cheese"')

        log.clear()

        # Trigger the group again, as past tasks, in a new flow.
        # It should flow on to task e again, in flow 2.
        await run_cmd(
            force_trigger_tasks(
                schd, ['1/a', '1/b', '1/c', '1/d', '1/xt'], ['new'])
        )
        await complete(schd, '1/e')

        assert log_filter(
            regex=(
                r"1/c\(flows=2\):waiting.*prerequisite"
                r" force-satisfied: xr = xrandom"
            )
        )
        assert log_filter(
            regex=(
                r"1/b\(flows=2\):waiting.*prerequisite"
                r" force-satisfied: 1/off:succeeded"
            )
        )
        assert log_filter(
            regex=(
                r"1/a\(flows=2\):waiting.*prerequisite"
                r" force-satisfied: 1/x:succeeded"
            )
        )
        assert log_filter(
            regex=(
                r"1/xt\(flows=2\):waiting.*external trigger"
                r' force-satisfied: "cheese"'
            )
        )

        # Task d (in the group) should have run 3 times.
        assert log_filter(
            contains="[1/d/03(flows=2):running] => succeeded"
        )
        # Task e (downstream of the group) only twice (once in each flow).
        assert log_filter(
            contains="[1/e/02(flows=2):running] => succeeded"
        )


async def test_trigger_active_task_in_group(
    flow,
    scheduler,
    run,
    complete,
    log_filter,
    reflog,
):
    """It should remove (and kill) active tasks that are not group start tasks.

    The workflow `a => b => c` starts out like this:

    * a (succeeded, n=1)
    * b (running, n=0)
    * c (waiting, n=1)

    Then we reload to add the dependency `d => b` and trigger a, b & c.

    * a - should be removed and re-spawned.
    * b - should be removed and re-spawned with `a => b` unsatisfied but
      `d => b` force-satisfied.
    * c - should be left alone.

    See point (4):
        https://github.com/cylc/cylc-admin/blob/master/docs/proposal-group-trigger.md#details
    """
    conf = {
        'scheduling': {
            'graph': {'R1': 'a => b => c'},
        },
    }
    id_ = flow(conf)
    schd = scheduler(id_, paused_start=False)

    async with run(schd):
        # capture triggering information
        triggers = reflog(schd)

        # run until 1/a:succeeded
        await complete(schd, '1/a')

        # check 1/b prereqs
        b_1 = schd.pool.get_task(IntegerPoint('1'), 'b')
        assert [
            (prereq.task, is_satisfied)
            for condition in b_1.state.prerequisites
            for prereq, is_satisfied in condition.items()
        ] == [
            # 1/b has a single prereq, it has been satisfied normally
            ('a', 'satisfied naturally'),
        ]

        # submit 1/b
        schd.submit_task_jobs([b_1])

        # reload the workflow adding the dependency "d => b"
        conf['scheduling']['graph']['R1'] += '\nd => b'
        flow(conf, workflow_id=id_)
        await run_cmd(reload_workflow(schd))

        # trigger the chain a => b => c
        await run_cmd(force_trigger_tasks(schd, ['1/a', '1/b', '1/c'], []))

        # active task 1/b should be killed
        assert log_filter(
            contains=(
                '[1/b/01:running] removed from the n=0 window: request'
                ' - active job orphaned'
            )
        )

        # check 1/b prereqs
        b_1 = schd.pool.get_task(IntegerPoint('1'), 'b')  # ret reloaded task
        assert [
            (prereq.task, is_satisfied)
            for condition in b_1.state.prerequisites
            for prereq, is_satisfied in condition.items()
        ] == [
            # in-group prereq has been reset
            ('a', False),
            # off-group prereq has been "force satisfied"
            ('d', 'force satisfied'),
        ]

        # the workflow should run the chain a => b => c as instructed
        await complete(schd, '1/c')
        assert triggers == {
            ('1/a', None),
            ('1/b', ('1/a',)),  # original run
            ('1/b', ('1/a', '1/d')),  # force-triggered run
            ('1/c', ('1/b',)),
        }


async def test_trigger_group_in_flow(
    flow,
    scheduler,
    run,
    complete,
    reflog,
    db_select,
):
    """It should remove tasks from the triggered flow(s).

    Tests the following statement from the proposal:

    > Use the same flow numbers, as determined by the trigger command in the
    > usual way, throughout the operation
    >
    > -- https://cylc.github.io/cylc-admin/proposal-group-trigger.html#details
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a => b => c => d'
            }
        }
    })
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # prevent shutdown after 1/c completes
        await run_cmd(hold(schd, ['1/d']))

        # run the chain, merge in flow "2" part way through
        triggers = reflog(schd, flow_nums=True)
        await complete(schd, '1/a')
        await run_cmd(force_trigger_tasks(schd, ['1/b'], ['2']))
        await complete(schd, '1/c')
        assert triggers == {
            # (task, flow_nums, triggered_off_of)
            ('1/a', '[1]', None),
            ('1/b', '[1, 2]', ('1/a',)),  # flow "2" merged in
            ('1/c', '[1, 2]', ('1/b',)),  # flow "2" merged in
        }

        # re-run the chain in flow "2"
        triggers = reflog(schd, flow_nums=True)
        await run_cmd(force_trigger_tasks(schd, ['1/a', '1/b', '1/c'], ['2']))
        await complete(schd, '1/c', timeout=10)
        assert triggers == {
            # (task, flow_nums, triggered_off_of)
            ('1/a', '[2]', None),
            ('1/b', '[2]', ('1/a',)),
            ('1/c', '[2]', ('1/b',)),
        }

        # ensure that flow "2" was removed from the tasks in the original run
        # by the group-trigger
        assert set(db_select(
            schd,
            True,
            'task_outputs',
            'name',
            'flow_nums',
        )) == {
            # original run
            ('a', '[1]'),
            ('b', '[1]'),  # flow "2" has been removed
            ('c', '[1]'),  # flow "2" has been removed
            ('d', '[1, 2]'),

            # subsequent run
            ('a', '[2]'),
            ('b', '[2]'),
            ('c', '[2]'),
        }


async def test_trigger_n0_tasks(
    flow,
    scheduler,
    run,
    complete,
    db_select,
):
    """It should trigger tasks within their flow if available, else all flows.

    * N=0 tasks already have a flow assigned.
    * N!=0 tasks do not yet have a flow assigned.

    When we are triggering n!=0 tasks, there is no appropriate flow to run them
    in (this would involve flow merge prediction), so we default to all active
    flows as the most/only sensible default.

    Before group trigger, we triggered tasks independently, i.e. we assumed
    there were no dependencies between the tasks and ran them all
    simultaneously. With the group trigger extension, we enhanced trigger to
    make it aware of interdependent tasks.

    Triggering independent tasks (pre group-trigger behaviour):
      * If we trigger a n=0 task, we leave it in the flow it is already in.
      * If we trigger a n!=0 task, we default to all active flows.

    Triggering interdependent tasks (group trigger extension):
      If the list of tasks being triggered contains any interdependent tasks,
      we treat these interdependent tasks as a group.

      * If we trigger a group which contains n=0 tasks, the whole group should
        be triggered using the set of flows possessed by these n=0 tasks.
      * If we trigger a group which does not contain n=0 tasks, we default to
        all active flows.
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '''
                    # group 1 (we will trigger a, b & c)
                    a => b => c => z

                    # group 2 (we will trigger e, f & g)
                    e => f => g => z

                    # group 3 (we will trigger y)
                    x => y => z
                '''
            }
        }
    })
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # cylc hold 1/x
        await run_cmd(hold(schd, ['1/x']))

        # group 1: spawn n>0 tasks into flows 2 & 3
        await run_cmd(
            set_prereqs_and_outputs(schd, ['1/b'], ['2'], None, ['all'])
        )
        await run_cmd(
            set_prereqs_and_outputs(schd, ['1/c'], ['3'], None, ['all'])
        )

        # group 2: spawn n>0 tasks into flows 4 & 5
        await run_cmd(
            set_prereqs_and_outputs(schd, ['1/f'], ['4'], None, ['all'])
        )
        await run_cmd(
            set_prereqs_and_outputs(schd, ['1/g'], ['5'], None, ['all'])
        )

        # trigger all three groups of tasks
        await run_cmd(
            force_trigger_tasks(
                schd, ['1/a', '1/b', '1/c', '1/e', '1/f', '1/g', '1/y'], []
            )
        )

        await complete(
            schd, '1/a', '1/b', '1/c', '1/e', '1/f', '1/g', '1/y', '1/z'
        )

        assert set(db_select(
            schd,
            True,
            'task_outputs',
            'name',
            'flow_nums',
        )) == {
            # junk entries inserted on spawn/set
            ('a', '[1]'),  # initial flow spawned on startup
            ('b', '[]'),   # created by "cylc set"
            ('c', '[]'),   # created by "cylc set"
            ('e', '[1]'),  # initial flow spawned on startup
            ('f', '[]'),   # created by "cylc set"
            ('g', '[]'),   # created by "cylc set"
            ('x', '[1]'),  # initial flow spawned on startup

            # group 1: contained tasks in flows 1, 2 & 3
            ('a', '[1, 2, 3]'),
            ('b', '[1, 2, 3]'),
            ('c', '[1, 2, 3]'),

            # group 2: contained tasks in flows 1, 4 & 5
            ('e', '[1, 4, 5]'),
            ('f', '[1, 4, 5]'),
            ('g', '[1, 4, 5]'),

            # group 3: contained tasks in flows None
            ('y', '[1, 2, 3, 4, 5]'),

            # downstream task
            ('z', '[1, 2, 3, 4, 5]'),
        }

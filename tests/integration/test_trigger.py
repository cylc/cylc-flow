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

"""Test for flow-assignment in triggered tasks."""

import time

from cylc.flow.flow_mgr import FLOW_NONE, FLOW_NEW, FLOW_ALL

async def test_trigger_no_flows(one, start, log_filter):
    """Test triggering a task with no flows present.

    It should get the flow numbers of the most recent active tasks.
    """
    async with start(one):

        # Remove the task (flow 1) --> pool empty
        task = one.pool.get_tasks()[0]
        one.pool.remove(task)
        assert len(one.pool.get_tasks()) == 0

        # Trigger the task, with new flow nums.
        time.sleep(2)  # The flows need different timestamps!
        one.pool.force_trigger_tasks([task.identity], [5, 9])
        assert len(one.pool.get_tasks()) == 1

        # Ensure the new flow is in the db.
        one.pool.workflow_db_mgr.process_queued_ops()

        # Remove the task --> pool empty
        task = one.pool.get_tasks()[0]
        one.pool.remove(task)
        assert len(one.pool.get_tasks()) == 0

        # Trigger the task; it should get flow nums 5, 9
        one.pool.force_trigger_tasks([task.identity], [FLOW_ALL])
        assert len(one.pool.get_tasks()) == 1
        task = one.pool.get_tasks()[0]
        assert task.flow_nums == {5, 9}


async def test_get_flow_nums(one, start, log_filter):
    """Test the task pool _get_flow_nums() method."""
    async with start(one):
        # flow 1 is already present
        task = one.pool.get_tasks()[0]
        two, = *one.pool._get_flow_nums([FLOW_NEW]),
        one.pool.merge_flows(task, set([two]))
        # now we have flows {1, 2}:

        assert one.pool._get_flow_nums([FLOW_NONE]) == set()
        assert one.pool._get_flow_nums([FLOW_ALL]) == set([1, two])
        assert one.pool._get_flow_nums([FLOW_NEW]) == set([3])
        assert one.pool._get_flow_nums([4, 5]) == set([4, 5])
        # the only active task still only has flows {1, 2}
        assert one.pool._get_flow_nums([FLOW_ALL]) == set([1, two])


async def test_trigger(flow, scheduler, start):
    """Test flow assignment when triggering tasks.

    Active tasks:
      By default keep existing flows, else merge with requested flows.
    Inactive tasks:
      By default assign active flows; else assign requested flows.

    """
    conf = {
        'scheduler': {
            'allow implicit tasks': 'True'
        },
        'scheduling': {
            'graph': {
                'R1': "foo & bar => a & b & c & d & e"
            }
        }
    }
    id_ = flow(conf)
    schd = scheduler(id_, run_mode='simulation', paused_start=True)
    async with start(schd):
        active_a, active_b = schd.pool.get_tasks()
        schd.pool.merge_flows(
            active_b, schd.pool._get_flow_nums([FLOW_NEW]))
        assert active_a.flow_nums == set([1])
        assert active_b.flow_nums == set([1, 2])

        #-----(1. Test active tasks)-----

        # By default active tasks keep existing flow assignment.
        schd.pool.force_trigger_tasks(
            [active_a.identity], flow=[]
        )
        assert active_a.flow_nums == set([1])

        # Else merge existing flow with requested flows.
        schd.pool.force_trigger_tasks(
            [active_a.identity], flow=[FLOW_ALL]
        )
        assert active_a.flow_nums == set([1, 2])

        # (no-flow is ignored for active tasks)
        schd.pool.force_trigger_tasks(
            [active_a.identity], flow=[FLOW_NONE]
        )
        assert active_a.flow_nums == set([1, 2])

        schd.pool.force_trigger_tasks(
            [active_a.identity], flow=[FLOW_NEW]
        )
        assert active_a.flow_nums == set([1, 2, 3])

        #-----(2. Test inactive tasks)-----

        # By default inactive tasks get all active flows.
        schd.pool.force_trigger_tasks(
            ['1/a'], flow=[]
        )
        assert schd.pool._get_task_by_id('1/a').flow_nums == set(
            [1, 2, 3]
        )

        # Else assign requested flows.
        schd.pool.force_trigger_tasks(
            ['1/b'], flow=[FLOW_NONE]
        )
        assert schd.pool._get_task_by_id('1/b').flow_nums == set([])

        schd.pool.force_trigger_tasks(
            ['1/c'], flow=[FLOW_NEW]
        )
        assert schd.pool._get_task_by_id('1/c').flow_nums == set([4])

        schd.pool.force_trigger_tasks(
            ['1/d'], flow=[FLOW_ALL]
        )
        assert schd.pool._get_task_by_id('1/d').flow_nums == set(
            [1, 2, 3, 4]
        )
        schd.pool.force_trigger_tasks(
            ['1/e'], flow=[7]
        )
        assert schd.pool._get_task_by_id('1/e').flow_nums == set([7])


async def test_set(flow, scheduler, start):
    """Test flow assignment when triggering tasks.

    Active tasks:
      By default keep existing flows, else merge with requested flows.
    Inactive tasks:
      By default assign active flows; else assign requested flows.

    """
    conf = {
        'scheduler': {
            'allow implicit tasks': 'True'
        },
        'scheduling': {
            'graph': {
                'R1': "foo & bar => a & b & c & d & e"
            }
        },
        'runtime': {
            'foo': {
                'outputs': { 'x': 'x' }
            }
        }
    }
    id_ = flow(conf)
    schd = scheduler(id_, run_mode='simulation', paused_start=True)
    async with start(schd):
        active_a, active_b = schd.pool.get_tasks()
        schd.pool.merge_flows(
            active_b, schd.pool._get_flow_nums([FLOW_NEW]))
        assert active_a.flow_nums == set([1])
        assert active_b.flow_nums == set([1, 2])

        #-----(1. Test active tasks)-----

        # By default active tasks keep existing flow assignment.
        schd.pool.set_prereqs_and_outputs(
            [active_a.identity], ['x'], [], flow=[]
        )
        assert active_a.flow_nums == set([1])

        # Else merge existing flow with requested flows.
        schd.pool.set_prereqs_and_outputs(
            [active_a.identity], ['x'], [], flow=[FLOW_ALL]
        )
        assert active_a.flow_nums == set([1, 2])

        # (no-flow is ignored for active tasks)
        schd.pool.set_prereqs_and_outputs(
            [active_a.identity], ['x'], [], flow=[FLOW_NONE]
        )
        assert active_a.flow_nums == set([1, 2])

        schd.pool.set_prereqs_and_outputs(
            [active_a.identity], ['x'], [], flow=[FLOW_NEW]
        )
        assert active_a.flow_nums == set([1, 2, 3])

        #-----(2. Test inactive tasks)-----

        # By default inactive tasks get all active flows.
        schd.pool.set_prereqs_and_outputs(
            ['1/a'], [], ['all'], flow=[]
        )
        assert schd.pool._get_task_by_id('1/a').flow_nums == set(
            [1, 2, 3]
        )

        # Else assign requested flows.
        schd.pool.set_prereqs_and_outputs(
            ['1/b'], [], ['all'], flow=[FLOW_NONE]
        )
        assert schd.pool._get_task_by_id('1/b').flow_nums == set([])

        schd.pool.set_prereqs_and_outputs(
            ['1/c'], [], ['all'], flow=[FLOW_NEW]
        )
        assert schd.pool._get_task_by_id('1/c').flow_nums == set([4])

        schd.pool.set_prereqs_and_outputs(
            ['1/d'], [], ['all'], flow=[FLOW_ALL]
        )
        assert schd.pool._get_task_by_id('1/d').flow_nums == set(
            [1, 2, 3, 4]
        )

        schd.pool.set_prereqs_and_outputs(
            ['1/e'], [], ['all'], flow=[7]
        )
        assert schd.pool._get_task_by_id('1/e').flow_nums == set([7])


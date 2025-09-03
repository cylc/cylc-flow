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

"""Test for flow-assignment in triggered/set tasks."""

import functools
import logging
import time
from typing import Callable

import pytest

from cylc.flow.flow_mgr import (
    FLOW_NEW,
    FLOW_NONE,
)
from cylc.flow.scheduler import Scheduler
from cylc.flow.commands import (
    run_cmd,
    force_trigger_tasks,
    set_prereqs_and_outputs,
)


async def test_trigger_no_flows(one, start):
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
        await run_cmd(
            force_trigger_tasks(one, [task.identity], flow=['5', '9']))
        assert len(one.pool.get_tasks()) == 1

        # Ensure the new flow is in the db.
        one.pool.workflow_db_mgr.process_queued_ops()

        # Remove the task --> pool empty
        task = one.pool.get_tasks()[0]
        one.pool.remove(task)
        assert len(one.pool.get_tasks()) == 0

        # Trigger the task; it should get flow nums 5, 9
        await run_cmd(force_trigger_tasks(one, [task.identity], []))
        assert len(one.pool.get_tasks()) == 1
        task = one.pool.get_tasks()[0]
        assert task.flow_nums == {5, 9}


async def test_cli_to_flow_nums(one: Scheduler, start):
    """Test the flow manager cli_to_flow_nums method."""
    async with start(one):
        # flow 1 is already present
        task = one.pool.get_tasks()[0]
        assert one.pool.flow_mgr.cli_to_flow_nums([FLOW_NEW]) == {2}
        one.pool.merge_flows(task, {2})
        # now we have flows {1, 2}:

        assert one.pool.flow_mgr.cli_to_flow_nums([FLOW_NONE]) == set()
        assert one.pool.flow_mgr.cli_to_flow_nums([]) == set()
        assert one.pool.flow_mgr.cli_to_flow_nums([FLOW_NEW]) == {3}
        assert one.pool.flow_mgr.cli_to_flow_nums(['4', '5']) == {4, 5}


@pytest.mark.parametrize('command', ['trigger', 'set'])
async def test_flow_assignment(
    flow, scheduler, start, command: str, log_filter: Callable
):
    """Test flow assignment when triggering/setting tasks.

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
                'outputs': {'x': 'x'}
            }
        },
    }
    id_ = flow(conf)
    schd: Scheduler = scheduler(id_, run_mode='simulation', paused_start=True)
    async with start(schd):
        if command == 'set':
            do_command = functools.partial(
                set_prereqs_and_outputs,
                schd,
                outputs=['x'],
                prerequisites=[],
            )
        else:
            do_command = functools.partial(
                force_trigger_tasks,
                schd,
            )

        active_1, active_2 = schd.pool.get_tasks()  # foo, bar in any order
        schd.pool.merge_flows(
            active_2, schd.pool.flow_mgr.cli_to_flow_nums([FLOW_NEW]))
        assert active_1.flow_nums == {1}
        assert active_2.flow_nums == {1, 2}

        # -----(1. Test active tasks)-----

        await run_cmd(do_command([active_1.identity], flow=[]))
        if command == "set":
            # By default active tasks merge existing and active flows.
            assert active_1.flow_nums == {1, 2}
        else:
            # By default active tasks keep existing flows.
            assert active_1.flow_nums == {1}

        # Else merge existing and requested flows.
        await run_cmd(do_command([active_1.identity], flow=['2']))
        assert active_1.flow_nums == {1, 2}

        # (no-flow is ignored for active tasks)
        await run_cmd(do_command([active_1.identity], flow=[FLOW_NONE]))
        assert active_1.flow_nums == {1, 2}
        assert log_filter(
            contains=("Already active - ignoring"),
            level=logging.WARNING
        )

        await run_cmd(do_command([active_1.identity], flow=[FLOW_NEW]))
        assert active_1.flow_nums == {1, 2, 3}

        # -----(2. Test inactive tasks)-----
        if command == 'set':
            do_command = functools.partial(
                set_prereqs_and_outputs,
                schd,
                outputs=[],
                prerequisites=['all'],
            )

        # By default inactive tasks get all active flows.
        await run_cmd(do_command(['1/a'], flow=[]))
        assert schd.pool._get_task_by_id('1/a').flow_nums == {1, 2, 3}

        # Else assign requested flows.
        # Run as no-flow:
        await run_cmd(do_command(['1/b'], flow=[FLOW_NONE]))
        assert schd.pool._get_task_by_id('1/b').flow_nums == set()

        await run_cmd(do_command(['1/c'], flow=[FLOW_NEW]))
        assert schd.pool._get_task_by_id('1/c').flow_nums == {4}

        await run_cmd(do_command(['1/d'], flow=[]))
        assert schd.pool._get_task_by_id('1/d').flow_nums == {1, 2, 3, 4}

        await run_cmd(do_command(['1/e'], flow=["7"]))
        assert schd.pool._get_task_by_id('1/e').flow_nums == {7}

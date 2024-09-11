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

from cylc.flow.flow_mgr import FLOW_ALL, FLOW_NEW, FLOW_NONE
from cylc.flow.command_validation import flow_opts
from cylc.flow.exceptions import InputError

import pytest
import time


@pytest.mark.parametrize(
    'flow_strs',
    (
        [FLOW_ALL, '1'],
        ['1', FLOW_ALL],
        [FLOW_NEW, '1'],
        [FLOW_NONE, '1'],
        ['a'],
        ['1', 'a'],
    )
)
async def test_trigger_invalid(mod_one, start, log_filter, flow_strs):
    """Ensure invalid flow values are rejected during command validation."""
    async with start(mod_one) as log:
        log.clear()
        with pytest.raises(InputError):
            flow_opts(flow_strs, False)


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

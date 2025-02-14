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


from typing import List
from unittest.mock import Mock

import pytest

from cylc.flow.flow_mgr import FlowNums
from cylc.flow.prerequisite import SatisfiedState
from cylc.flow.task_pool import TaskPool


@pytest.mark.parametrize('pool, db_fnums, expected', [
    pytest.param(
        [{1, 2}, {2, 3}],
        {5, 6},
        {1, 2, 3},
        id="all-active"
    ),
    pytest.param(
        [set(), set()],
        {5, 6},
        {5, 6},
        id="from-db"
    ),
    pytest.param(
        [set()],
        set(),
        {1},
        id="fallback"  # see https://github.com/cylc/cylc-flow/pull/6445
    ),
])
def test_get_active_flow_nums(
    pool: List[FlowNums], db_fnums: FlowNums, expected
):
    mock_task_pool = Mock(
        get_tasks=lambda: [Mock(flow_nums=fnums) for fnums in pool],
    )
    mock_task_pool.workflow_db_mgr.pri_dao.select_latest_flow_nums = (
        lambda: db_fnums
    )

    assert TaskPool._get_active_flow_nums(mock_task_pool) == expected


@pytest.mark.parametrize('output_msg, flow_nums, db_flow_nums, expected', [
    ('foo', set(), {1}, False),
    ('foo', set(), set(), False),
    ('foo', {1, 3}, {1}, 'satisfied from database'),
    ('goo', {1, 3}, {1, 2}, 'satisfied from database'),
    ('foo', {1, 3}, set(), False),
    ('foo', {2}, {1}, False),
    ('foo', {2}, {1, 2}, 'satisfied from database'),
    ('f', {1}, {1}, False),
])
def test_check_output(
    output_msg: str,
    flow_nums: set,
    db_flow_nums: set,
    expected: SatisfiedState,
):
    mock_task_pool = Mock()
    mock_task_pool.workflow_db_mgr.pri_dao.select_task_outputs.return_value = {
        '{"f": "foo", "g": "goo"}': db_flow_nums,
    }

    assert TaskPool.check_task_output(
        mock_task_pool, '2000', 'haddock', output_msg, flow_nums
    ) == expected

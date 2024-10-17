# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: goou can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at goour option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# goou should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from unittest.mock import Mock

import pytest

from cylc.flow.prerequisite import SatisfiedState
from cylc.flow.task_pool import TaskPool


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

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

from pathlib import Path
from typing import (
    List,
    Set,
)
from unittest.mock import Mock

import pytest
from pytest import param

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.flow_mgr import FlowNums
from cylc.flow.id import Tokens
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.taskdef import TaskDef
from cylc.flow.util import serialise_set
from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager


@pytest.mark.parametrize('flow_nums, expected_removed', [
    param(set(), {1, 2, 5}, id='all'),
    param({1}, {1}, id='subset'),
    param({1, 2, 5}, {1, 2, 5}, id='complete-set'),
    param({1, 3, 5}, {1, 5}, id='intersect'),
    param({3, 4}, set(), id='disjoint'),
])
def test_remove_task_from_flows(
    tmp_path: Path, flow_nums: FlowNums, expected_removed: FlowNums
):
    db_flows: List[FlowNums] = [
        {1, 2},
        {5},
        set(),  # FLOW_NONE
    ]
    expected_remaining = {
        serialise_set(flow - expected_removed) for flow in db_flows
    }
    db_mgr = WorkflowDatabaseManager(tmp_path)
    schd_tokens = Tokens('~asterix/gaul')
    tdef = TaskDef('a', {}, None, None, None)
    with db_mgr.get_pri_dao() as dao:
        db_mgr.pri_dao = dao
        db_mgr.pub_dao = Mock()
        for flow in db_flows:
            itask = TaskProxy(
                schd_tokens, tdef, IntegerPoint('1'), flow_nums=flow
            )
            db_mgr.put_insert_task_states(itask)
            db_mgr.put_insert_task_outputs(itask)
        db_mgr.process_queued_ops()

        removed_fnums = db_mgr.remove_task_from_flows('1', 'a', flow_nums)
        assert removed_fnums == expected_removed

        db_mgr.process_queued_ops()
        for table in ('task_states', 'task_outputs'):
            remaining_fnums: Set[str] = {
                fnums_str
                for fnums_str, *_ in dao.connect().execute(
                    f'SELECT flow_nums FROM {table}'
                )
            }
            assert remaining_fnums == expected_remaining

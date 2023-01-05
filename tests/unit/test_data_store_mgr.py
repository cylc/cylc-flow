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

from copy import deepcopy
from time import time

from cylc.flow.data_store_mgr import (
    task_mean_elapsed_time,
    apply_delta,
    WORKFLOW,
    DELTAS_MAP,
    ALL_DELTAS,
    DATA_TEMPLATE
)


def int_id():
    return '20130808T00/foo/03'


class FakeTDef:
    elapsed_times = (0.0, 10.0)


def test_task_mean_elapsed_time():
    tdef = FakeTDef()
    result = task_mean_elapsed_time(tdef)
    assert result == 5
    assert isinstance(result, int)


def test_apply_delta():
    """Test delta application.

    Some functionality is not used at the Scheduler, so is not covered
    by integration testing.

    """
    w_id = 'workflow_id'
    delta = DELTAS_MAP[ALL_DELTAS]()
    delta.workflow.time = time()
    flow = delta.workflow.updated
    flow.id = 'workflow_id'
    flow.stamp = f'{w_id}@{delta.workflow.time}'
    delta.workflow.pruned = w_id

    data = deepcopy(DATA_TEMPLATE)

    assert data[WORKFLOW].id != w_id
    assert data[WORKFLOW].pruned is False

    for field, sub_delta in delta.ListFields():
        apply_delta(field.name, sub_delta, data)

    assert data[WORKFLOW].id == w_id
    assert data[WORKFLOW].pruned is True

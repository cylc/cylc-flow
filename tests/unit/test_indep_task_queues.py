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
#
# Tests for the task queue manager module

from collections import Counter
from unittest.mock import Mock

import pytest

from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_queues.independent import IndepQueueManager


MEMBERS = {"a", "b", "c", "d", "e", "f"}
ACTIVE = Counter(["a", "a", "d"])

ALL_TASK_NAMES = [
    "o1", "o2", "o3", "o4", "o5", "o6", "o7",
    "s1", "s2", "s3", "s4", "s5",
    "b1", "b2", "b3", "b4", "b5",
    "foo"
]

DESCENDANTS = {
    "root": ALL_TASK_NAMES + ["BIG", "SML", "OTH", "foo"],
    "BIG": ["b1", "b2", "b3", "b4", "b5"],
    "SML": ["s1", "s2", "s3", "s4", "s5"],
    "OTH": ["o1", "o2", "o3", "o4", "o5", "o6", "o7"]
}

QCONFIG = {
    "default": {
        "limit": 6,
        "members": []  # (auto: all task names)
    },
    "big": {
        "members": ["BIG", "foo"],
        "limit": 2
    },
    "sml": {
        "members": ["SML", "foo"],
        "limit": 3
    }
}

READY_TASK_NAMES = ["b3", "s4", "o2", "s3", "b4", "o3", "o4", "o5", "o6", "o7"]


@pytest.mark.parametrize(
    "active, expected_released, expected_foo_groups",
    [
        (
            Counter(["b1", "b2", "s1", "o1"]),
            ["s4", "o2", "s3", "o3", "o4", "o5", "o6"],
            ["sml"]
        )
    ]
)
def test_queue_and_release(
    active,
    expected_released,
    expected_foo_groups
):
    """Test task queue and release."""
    # configure the queue
    queue_mgr = IndepQueueManager(QCONFIG, ALL_TASK_NAMES, DESCENDANTS)

    # add newly ready tasks to the queue
    for name in READY_TASK_NAMES:
        itask = Mock(spec=TaskProxy)
        itask.tdef.name = name
        itask.state.is_held = False
        queue_mgr.push_task(itask)

    # release tasks, given current active task counter
    released = queue_mgr.release_tasks(active)
    assert sorted(r.tdef.name for r in released) == sorted(expected_released)

    # check that adopted orphans end up in the default queue
    orphans = ["orphan1", "orphan2"]
    queue_mgr.adopt_tasks(orphans)
    for orphan in orphans:
        assert orphan in queue_mgr.queues["default"].members

    # check second assignment overrides first
    for group in expected_foo_groups:
        assert "foo" in queue_mgr.queues[group].members

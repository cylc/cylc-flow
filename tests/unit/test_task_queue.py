# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
# Tests for the task queue module

import pytest
from unittest.mock import Mock
from collections import Counter
from cylc.flow.task_queue import TaskQueue, Limiter
from cylc.flow.task_state import TASK_STATUS_PREPARING


MEMBERS = {"a", "b", "c", "d", "e", "f"}
ACTIVE = Counter(["a", "a", "d"])


@pytest.mark.parametrize(
    "limit,task_name,expected",
    [
        (  # limited: limit reached
            3,
            "c",
            True
        ),
        (  # not limited: not a member
            3,
            "g",
            False
        ),
        (  # not limited: limit not reached
            4,
            "c",
            False
        )
    ]
)
def test_limiter(limit, task_name, expected):
    """Test the queue limiter."""
    itask = Mock()
    itask.tdef.name = task_name
    limiter = Limiter(limit, MEMBERS)
    assert limiter.is_limited(itask, ACTIVE) == expected


def test_limiter_adopt():
    """Test queue limiter adoption."""
    limiter = Limiter(3, MEMBERS)
    itask = Mock()
    itask.tdef.name = "g"
    # not limited: not a member
    assert not limiter.is_limited(itask, ACTIVE)
    limiter.adopt(["g"])
    # limited: is now a member
    assert limiter.is_limited(itask, ACTIVE)


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
    "type": None,
    "default": {
        "limit": 6,
        "members": []  # (populated with all tasks, in TaskQueue init)
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
    "queue_type,"
    "active,"
    "expected_released,"
    "expected_still_queued,"
    "expected_foo_groups",
    [
        (
            "overlapping",
            Counter(["b1", "b2", "s1", "o1"]),
            ["s4", "o2"],
            ["b3", "s3", "b4", "o3", "o4", "o5", "o6", "o7"],
            ["big", "sml"]
        ),
        (
            "classic",
            Counter(["b1", "b2", "s1", "o1"]),
            ["s4", "o2", "s3", "o3", "o4", "o5", "o6"],
            ["b3", "b4", "o7"],
            ["sml"]
        )
    ]
)
def test_queue_and_release(
        queue_type,
        active,
        expected_released,
        expected_still_queued,
        expected_foo_groups):
    """Test task queue and release."""
    # configure the queue
    QCONFIG["type"] = queue_type
    queue = TaskQueue(QCONFIG, ALL_TASK_NAMES, DESCENDANTS)

    # add newly ready tasks to the queue
    for name in READY_TASK_NAMES:
        itask = Mock()
        itask.tdef.name = name
        queue.add(itask)
        itask.state.reset.assert_called_with(is_queued=True)
        itask.reset_manual_trigger.assert_called()

    # release tasks, given current active task counter
    released = queue.release(active)
    assert [r.tdef.name for r in released] == expected_released

    # check released tasks change state to "preparing", and not is_queued
    for r in released:
        assert r.state.reset.called_with(TASK_STATUS_PREPARING)
        assert r.state.reset.called_with(is_queued=False)

    # check unreleased tasks pushed back in the correct order
    assert (
        [r.tdef.name for r in reversed(queue.task_deque)] ==
        expected_still_queued
    )

    # check that adopted orphans end up in the default queue
    orphans = ["orphan1", "orphan2"]
    queue.adopt_orphans(orphans)
    for orphan in orphans:
        assert orphan in queue.limiters["default"].members

    # check multiply-assigned "foo" ends up in expected groups (overlapping:
    # all assigned groups; classic: only the last assignment sticks)
    for group in expected_foo_groups:
        assert "foo" in queue.limiters[group].members

#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import pytest
import unittest

from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.taskdef import TaskDef
from cylc.flow.task_state import (
    TaskState,
    TASK_STATUS_RETRYING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
)


class TestTaskState(unittest.TestCase):

    def test_reset(self):
        """Test instantiation and simple resets."""
        point = ISO8601Point('2020')
        taskdef = TaskDef('who-cares', {}, 'live', point, False)
        taskstate = TaskState(taskdef, point, TASK_STATUS_WAITING, False)
        self.assertIsNone(
            taskstate.reset(TASK_STATUS_WAITING),
            'same status returns None',
        )
        self.assertEqual(
            taskstate.reset(TASK_STATUS_SUCCEEDED),
            (TASK_STATUS_WAITING, False),
            'different status returns previous (status, hold_swap)',
        )
        self.assertEqual(
            (taskstate.status, taskstate.is_held),
            (TASK_STATUS_SUCCEEDED, False),
            'reset status OK',
        )

    def test_reset_respect_hold_swap(self):
        point = ISO8601Point('2020')
        taskdef = TaskDef('who-cares', {}, 'live', point, False)
        taskstate = TaskState(
            taskdef, point, TASK_STATUS_RETRYING, is_held=True)
        self.assertIsNone(
            taskstate.reset(TASK_STATUS_RETRYING),
            'same status returns None',
        )
        self.assertEqual(
            taskstate.reset(TASK_STATUS_SUCCEEDED),
            (TASK_STATUS_RETRYING, True),
            'different status returns previous (status, hold_swap)',
        )
        self.assertEqual(
            (taskstate.status, taskstate.is_held),
            (TASK_STATUS_SUCCEEDED, True),
            'reset status OK',
        )


@pytest.mark.parametrize(
    'state,is_held',
    [
        (TASK_STATUS_WAITING, True),
        (TASK_STATUS_SUCCEEDED, False)
    ]
)
def test_state_comparison(state, is_held):
    tdef = TaskDef('foo', {}, 'live', '123', True)
    tstate = TaskState(tdef, '123', state, is_held)

    assert tstate(state, is_held=is_held)
    assert tstate(state)
    assert tstate(is_held=is_held)
    assert tstate(state, 'of', 'flux')
    assert tstate(state, 'of', 'flux', is_held=is_held)

    assert not tstate(state + 'x', is_held=not is_held)
    assert not tstate(state, is_held=not is_held)
    assert not tstate(state + 'x', is_held=is_held)
    assert not tstate(state + 'x')
    assert not tstate(is_held=not is_held)
    assert not tstate(state + 'x', 'of', 'flux')


if __name__ == '__main__':
    unittest.main()

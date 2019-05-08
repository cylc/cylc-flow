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

import unittest

from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.taskdef import TaskDef
from cylc.flow.task_state import (
    TaskState,
    TASK_STATUS_HELD,
    TASK_STATUS_RETRYING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
)


class TestTaskState(unittest.TestCase):

    def test_reset_state(self):
        """Test instantiation and simple resets."""
        point = ISO8601Point('2020')
        taskdef = TaskDef('who-cares', {}, 'live', point, False)
        taskstate = TaskState(taskdef, point, TASK_STATUS_WAITING, None)
        self.assertIsNone(
            taskstate.reset_state(TASK_STATUS_WAITING),
            'same status returns None',
        )
        self.assertEqual(
            taskstate.reset_state(TASK_STATUS_SUCCEEDED),
            (TASK_STATUS_WAITING, None),
            'different status returns previous (status, hold_swap)',
        )
        self.assertEqual(
            (taskstate.status, taskstate.hold_swap),
            (TASK_STATUS_SUCCEEDED, None),
            'reset status OK',
        )

    def test_reset_state_respect_hold_swap(self):
        point = ISO8601Point('2020')
        taskdef = TaskDef('who-cares', {}, 'live', point, False)
        taskstate = TaskState(
            taskdef, point, TASK_STATUS_HELD, TASK_STATUS_RETRYING)
        self.assertIsNone(
            taskstate.reset_state(
                TASK_STATUS_RETRYING, respect_hold_swap=True),
            'same status returns None',
        )
        self.assertEqual(
            taskstate.reset_state(
                TASK_STATUS_SUCCEEDED, respect_hold_swap=True),
            (TASK_STATUS_HELD, TASK_STATUS_RETRYING),
            'different status returns previous (status, hold_swap)',
        )
        self.assertEqual(
            (taskstate.status, taskstate.hold_swap),
            (TASK_STATUS_SUCCEEDED, None),
            'reset status OK',
        )


if __name__ == '__main__':
    unittest.main()

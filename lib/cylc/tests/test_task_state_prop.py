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

from cylc.task_state_prop import *


def get_test_extract_group_state_order():
    return [
        (
            [TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_FAILED],
            False,
            TASK_STATUS_SUBMIT_FAILED
        ),
        (
            ["Who?", TASK_STATUS_FAILED],
            False,
            TASK_STATUS_FAILED
        ),
        (
            [TASK_STATUS_RETRYING, TASK_STATUS_RUNNING],
            False,
            TASK_STATUS_RETRYING
        ),
        (
            [TASK_STATUS_RETRYING, TASK_STATUS_RUNNING],
            True,
            TASK_STATUS_RUNNING
        ),
    ]


def get_test_get_status_prop():
    return [
        (
            TASK_STATUS_HELD,
            "ascii_ctrl",
            "ace",
            "ace"
        ),
        (
            TASK_STATUS_HELD,
            "ascii_ctrl",
            None,
            TASK_STATUS_HELD
        )
    ]


class TestTaskStateProp(unittest.TestCase):

    def test_extract_group_state_childless(self):
        self.assertTrue(extract_group_state(child_states=[]) is None)

    def test_extract_group_state_order(self):
        params = get_test_extract_group_state_order()
        for child_states, is_stopped, expected in params:
            r = extract_group_state(child_states=child_states,
                                    is_stopped=is_stopped)
            self.assertEqual(expected, r)

    def test_get_status_prop(self):
        params = get_test_get_status_prop()
        for status, key, subst, expected in params:
            r = get_status_prop(status=status, key=key, subst=subst)
            self.assertTrue(expected in r)


if __name__ == '__main__':
    unittest.main()

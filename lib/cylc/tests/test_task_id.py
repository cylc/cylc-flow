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

from cylc.task_id import TaskID


class TestTaskId(unittest.TestCase):

    def test_get(self):
        self.assertEqual("a.1", TaskID.get("a", 1))
        self.assertEqual("a._1", TaskID.get("a", "_1"))
        self.assertEqual(
            "WTASK.20101010T101010", TaskID.get("WTASK", "20101010T101010"))

    def test_split(self):
        self.assertEqual(["a", '1'], TaskID.split("a.1"))
        self.assertEqual(["a", '_1'], TaskID.split("a._1"))
        self.assertEqual(
            ["WTAS", '20101010T101010'], TaskID.split("WTAS.20101010T101010"))

    def test_is_valid_name(self):
        for name in [
            "abc", "123", "____", "_", "a_b", "a_1", "1_b", "ABC"
        ]:
            self.assertTrue(TaskID.is_valid_name(name))
        for name in [
            "a.1", None, "%abc", "", " "
        ]:
            self.assertFalse(TaskID.is_valid_name(name))

    def test_is_valid_id(self):
        for id1 in [
            "a.1", "_.098098439535$#%#@!#~"
        ]:
            self.assertTrue(TaskID.is_valid_id(id1))
        for id2 in [
            "abc", "123", "____", "_", "a_b", "a_1", "1_b", "ABC", "a.A A"
        ]:
            self.assertFalse(TaskID.is_valid_id(id2))

    def test_is_valid_id_2(self):
        # TBD: a.A A is invalid for valid_id, but valid for valid_id_2?
        # TBD: a/a.a is OK?
        for id1 in [
            "a.1", "_.098098439535$#%#@!#~", "a/1", "_/098098439535$#%#@!#~",
            "a.A A", "a/a.a"
        ]:
            self.assertTrue(TaskID.is_valid_id_2(id1))
        for id2 in [
            "abc", "123", "____", "_", "a_b", "a_1", "1_b", "ABC"
        ]:
            self.assertFalse(TaskID.is_valid_id_2(id2))


if __name__ == '__main__':
    unittest.main()

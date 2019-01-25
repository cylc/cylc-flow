#!/usr/bin/env python2
# -*- coding: ascii -*-

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

from cylc.unicode_util import utf8_enforce


class TestUnicodeUtil(unittest.TestCase):

    def test_utf8_encode_nothing_to_encode(self):
        self.assertEqual("d", utf8_enforce("d"))

    def test_utf8_encode(self):
        value = str("d?")
        self.assertEqual("d?", utf8_enforce(value))

    def test_utf8_encode_with_dictionary(self):
        value = str("d?")
        d = {
            "simple": "d",
            "complex": value
        }
        expected = {
            "simple": "d",
            "complex": "d?"
        }
        self.assertEqual(expected, utf8_enforce(d))

    def test_utf8_encode_with_list(self):
        value = str("d?")
        d = ["d", value]
        expected = ["d", "d?"]
        self.assertEqual(expected, utf8_enforce(d))


if __name__ == '__main__':
    unittest.main()

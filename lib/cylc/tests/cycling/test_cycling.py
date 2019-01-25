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

from cylc.cycling import SequenceBase, IntervalBase, PointBase, parse_exclusion


class TestBaseClasses(unittest.TestCase):
    """Test the abstract base classes cannot be instantiated on their own
    """

    def test_simple_abstract_class_test(self):
        """Cannot instantiate abstract classes, they must be defined in
        the subclasses"""
        self.assertRaises(TypeError, SequenceBase, "sequence-string",
                          "context_string")
        self.assertRaises(TypeError, IntervalBase, "value")
        self.assertRaises(TypeError, PointBase, "value")


class TestParseExclusion(unittest.TestCase):
    """Test cases for the parser function"""

    def test_parse_exclusion_simple(self):
        """Tests the simple case of exclusion parsing"""
        expression = "PT1H!20000101T02Z"
        sequence, exclusion = parse_exclusion(expression)

        self.assertEqual(sequence, "PT1H")
        self.assertEqual(exclusion, ['20000101T02Z'])

    def test_parse_exclusions_list(self):
        """Tests the simple case of exclusion parsing"""
        expression = "PT1H!(T03, T06, T09)"
        sequence, exclusion = parse_exclusion(expression)

        self.assertEqual(sequence, "PT1H")
        self.assertEqual(exclusion, ['T03', 'T06', 'T09'])

    def test_parse_exclusions_list_spaces(self):
        """Tests the simple case of exclusion parsing"""
        expression = "PT1H!    (T03, T06,   T09)   "
        sequence, exclusion = parse_exclusion(expression)

        self.assertEqual(sequence, "PT1H")
        self.assertEqual(exclusion, ['T03', 'T06', 'T09'])

    def test_parse_bad_exclusion(self):
        """Tests incorrectly formatted exclusions"""
        expression1 = "T01/PT1H!(T06, T09), PT5M"
        expression2 = "T01/PT1H!T03, PT17H, (T06, T09), PT5M"
        expression3 = "T01/PT1H! PT8H, (T06, T09)"
        expression4 = "T01/PT1H! T03, T06, T09"

        self.assertRaises(Exception, parse_exclusion, expression1)
        self.assertRaises(Exception, parse_exclusion, expression2)
        self.assertRaises(Exception, parse_exclusion, expression3)
        self.assertRaises(Exception, parse_exclusion, expression4)


if __name__ == "__main__":
    unittest.main()

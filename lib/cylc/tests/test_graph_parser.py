#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

from cylc.graph_parser import GraphParser, GraphParseError


class TestGraphParser(unittest.TestCase):
    """Tests for Cylc's GraphParser"""

    def setUp(self):
        self.parser = GraphParser()

    def test_parse_graph_fails_if_starts_with_arrow(self):
        """Test that the graph parse will fail when the graph starts with an
        arrow."""
        with self.assertRaises(GraphParseError):
            self.parser.parse_graph("=> b")

    def test_parse_graph_fails_if_ends_with_arrow(self):
        """Test that the graph parse will fail when the graph ends with an
        arrow."""
        with self.assertRaises(GraphParseError):
            self.parser.parse_graph("a =>")

    def test_parse_graph_fails_with_spaces_in_task_name(self):
        """Test that the graph parse will fail when the task name contains
        spaces."""
        with self.assertRaises(GraphParseError):
            self.parser.parse_graph("a b => c")

    def test_parse_graph_fails_with_invalid_and_operator(self):
        """Test that the graph parse will fail when the and operator is not
        correctly used."""
        with self.assertRaises(GraphParseError):
            self.parser.parse_graph("a => c &&")

    def test_parse_graph_fails_with_invalid_or_operator(self):
        """Test that the graph parse will fail when the or operator is not
        correctly used."""
        with self.assertRaises(GraphParseError):
            self.parser.parse_graph("a => c ||")

    def test_parse_graph_simple(self):
        """Test parsing graphs."""
        # added white spaces and comments to show that these change nothing
        self.parser.parse_graph('a => b\n  \n# this is a comment\n')
        original = self.parser.original
        triggers = self.parser.triggers
        families = self.parser.family_map
        self.assertEqual(
            {'a': {'': ''}, 'b': {'a:succeed': 'a:succeed'}},
            original
        )
        self.assertEqual(
            {'a': {'': ([], False)},
             'b': {'a:succeed': (['a:succeed'], False)}},
            triggers
        )
        self.assertEqual({}, families)

    def test_parse_graph_simple_with_break_line_01(self):
        """Test parsing graphs."""
        self.parser.parse_graph('a => b\n'
                                '=> c')
        original = self.parser.original
        triggers = self.parser.triggers
        families = self.parser.family_map

        self.assertEqual({'': ''}, original['a'])
        self.assertEqual({'a:succeed': 'a:succeed'}, original['b'])
        self.assertEqual({'b:succeed': 'b:succeed'}, original['c'])

        self.assertEqual({'': ([], False)}, triggers['a'])
        self.assertEqual({'a:succeed': (['a:succeed'], False)}, triggers['b'])
        self.assertEqual({'b:succeed': (['b:succeed'], False)}, triggers['c'])

        self.assertEqual({}, families)

    def test_parse_graph_simple_with_break_line_02(self):
        """Test parsing graphs."""
        self.parser.parse_graph('a => b\n'
                                '=> c =>\n'
                                'd')
        original = self.parser.original
        triggers = self.parser.triggers
        families = self.parser.family_map

        self.assertEqual({'': ''}, original['a'])
        self.assertEqual({'a:succeed': 'a:succeed'}, original['b'])
        self.assertEqual({'b:succeed': 'b:succeed'}, original['c'])
        self.assertEqual({'c:succeed': 'c:succeed'}, original['d'])

        self.assertEqual({'': ([], False)}, triggers['a'])
        self.assertEqual({'a:succeed': (['a:succeed'], False)}, triggers['b'])
        self.assertEqual({'b:succeed': (['b:succeed'], False)}, triggers['c'])
        self.assertEqual({'c:succeed': (['c:succeed'], False)}, triggers['d'])

        self.assertEqual({}, families)

    # --- parameterized graphs

    def test_parse_graph_with_parameters(self):
        """Test parsing graphs with parameters."""
        parameterized_parser = GraphParser(
            None, ({'city': ['la_paz']}, {'city': '_%(city)s'}))
        parameterized_parser.parse_graph('a => b<city>')
        original = parameterized_parser.original
        triggers = parameterized_parser.triggers
        families = parameterized_parser.family_map
        self.assertEqual(
            {'a': {'': ''}, 'b_la_paz': {'a:succeed': 'a:succeed'}},
            original
        )
        self.assertEqual(
            {'a': {'': ([], False)},
             'b_la_paz': {'a:succeed': (['a:succeed'], False)}},
            triggers
        )
        self.assertEqual({}, families)

    def test_parse_graph_with_invalid_parameters(self):
        """Test parsing graphs with invalid parameters."""
        parameterized_parser = GraphParser(
            None, ({'city': ['la_paz']}, {'city': '_%(city)s'}))
        with self.assertRaises(GraphParseError):
            # no state in the parameters list
            parameterized_parser.parse_graph('a => b<state>')

    # --- inter-suite dependence

    def test_inter_suite_dependence_simple(self):
        """Test invalid inter-suite dependence"""
        self.parser.parse_graph('a<SUITE::TASK:fail> => b')
        original = self.parser.original
        triggers = self.parser.triggers
        families = self.parser.family_map
        suite_state_polling_tasks = self.parser.suite_state_polling_tasks
        self.assertEqual(
            {'a': {'': ''}, 'b': {'a:succeed': 'a:succeed'}},
            original
        )
        self.assertEqual(
            {'a': {'': ([], False)},
             'b': {'a:succeed': (['a:succeed'], False)}},
            triggers
        )
        self.assertEqual({}, families)
        self.assertEqual(('SUITE', 'TASK', 'fail', '<SUITE::TASK:fail>'),
                         suite_state_polling_tasks['a'])


if __name__ == '__main__':
    unittest.main()

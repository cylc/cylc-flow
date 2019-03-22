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

from cylc.conditional_simplifier import ConditionalSimplifier


class TestConditionalSimplifier(unittest.TestCase):
    """Test the Cylc ConditionalSimplifier"""

    def test_nest_by_oper_simple(self):
        """Test the case where we have a simple expression."""
        nested_expr = ConditionalSimplifier.nest_by_oper(['a', '||', 'b',
                                                          '||', 'c'], '||')
        self.assertIsInstance(nested_expr, list)
        self.assertEqual([['a', '||', 'b'], '||', 'c'], nested_expr)

    def test_nest_by_oper_with_arrays(self):
        """Test and expression with arrays (combined expressions)."""
        nested_expr = ConditionalSimplifier.nest_by_oper(
            [['a', '&', 'b'], '&', ['b', '&', 'c']], '&')
        self.assertIsInstance(nested_expr, list)
        self.assertEqual([['a', '&', 'b'], '&', ['b', '&', 'c']],
                         nested_expr)

    def test_nest_by_oper_not_matching_operator(self):
        """Test when the operation is simply not found. Same input returned."""
        input_expr = ['a', 'xor', 'b', 'not', 'c']
        nested_expr = ConditionalSimplifier.nest_by_oper(input_expr, 'mod')
        self.assertIsInstance(nested_expr, list)
        self.assertEqual(input_expr, nested_expr)

    def test_flatten_nested_expr(self):
        """Test flattened expressions"""
        flattened = ConditionalSimplifier.flatten_nested_expr(['a', '&', 'b'])
        self.assertEqual('(a & b)', flattened)

    def test_flatten_nested_expr_with_arrays(self):
        """Test flattened expressions with nested arrays"""
        flattened = ConditionalSimplifier.flatten_nested_expr(
            [['a', '&', 'b'], '&', 'c'])
        self.assertEqual('((a & b) & c)', flattened)

    get_clean_expr = [
        [[], None, []],
        [['a'], None, 'a'],
        [['a'], 'a', ""],
        [['a', '&', 'b'], 'b', "a"],
        [[['a', '&', 'b'], '&', 'c'], '&', 'c'],
        [['foo', '|', 'bar', '|'], 'foo', ['bar', '|']],
        [[['a', '&', 'b']], 'a', 'b']
    ]

    def test_clean_expr(self):
        """Test clean expressions"""
        for expr, criterion, expected in self.get_clean_expr:
            self.assertEqual(expected,
                             ConditionalSimplifier.clean_expr(expr, criterion))

    def test_flatten_nested_expr_with_brackets(self):
        """Test expressions with brackets"""
        bracketed = ConditionalSimplifier.get_bracketed(
            ['(', 'a', '&', 'b', ')'])
        self.assertEqual(['(', ['a', '&', 'b'], ')'], bracketed)


if __name__ == '__main__':
    unittest.main()

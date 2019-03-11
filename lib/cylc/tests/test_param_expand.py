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

from cylc.exceptions import ParamExpandError
from cylc.param_expand import NameExpander, GraphExpander


class TestParamExpand(unittest.TestCase):
    """Unit tests for the parameter expansion module."""

    def setUp(self):
        """Create some parameters and templates for use in tests."""
        params_map = {'a': [-3, -1], 'i': [0, 1], 'j': [0, 1, 2], 'k': [0, 1]}
        # k has template is deliberately bad
        templates = {
            'a': '_a%(a)d', 'i': '_i%(i)d', 'j': '_j%(j)d', 'k': '_k%(z)d'}
        self.name_expander = NameExpander((params_map, templates))
        self.graph_expander = GraphExpander((params_map, templates))

    def test_name_one_param(self):
        """Test name expansion and returned value for a single parameter."""
        self.assertEqual(
            self.name_expander.expand('foo<j>'),
            [('foo_j0', {'j': 0}),
             ('foo_j1', {'j': 1}),
             ('foo_j2', {'j': 2})]
        )

    def test_name_two_params(self):
        """Test name expansion and returned values for two parameters."""
        self.assertEqual(
            self.name_expander.expand('foo<i,j>'),
            [('foo_i0_j0', {'i': 0, 'j': 0}),
             ('foo_i0_j1', {'i': 0, 'j': 1}),
             ('foo_i0_j2', {'i': 0, 'j': 2}),
             ('foo_i1_j0', {'i': 1, 'j': 0}),
             ('foo_i1_j1', {'i': 1, 'j': 1}),
             ('foo_i1_j2', {'i': 1, 'j': 2})]
        )

    def test_name_two_names(self):
        """Test name expansion for two names."""
        self.assertEqual(
            self.name_expander.expand('foo<i>, bar<j>'),
            [('foo_i0', {'i': 0}),
             ('foo_i1', {'i': 1}),
             ('bar_j0', {'j': 0}),
             ('bar_j1', {'j': 1}),
             ('bar_j2', {'j': 2})]
        )

    def test_name_specific_val_1(self):
        """Test singling out a specific value, in name expansion."""
        self.assertEqual(
            self.name_expander.expand('foo<i=0>'),
            [('foo_i0', {'i': 0})]
        )

    def test_name_specific_val_2(self):
        """Test specific value in the first parameter of a pair."""
        self.assertEqual(
            self.name_expander.expand('foo<i=0,j>'),
            [('foo_i0_j0', {'i': 0, 'j': 0}),
             ('foo_i0_j1', {'i': 0, 'j': 1}),
             ('foo_i0_j2', {'i': 0, 'j': 2})]
        )

    def test_name_specific_val_3(self):
        """Test specific value in the second parameter of a pair."""
        self.assertEqual(
            self.name_expander.expand('foo<i,j=1>'),
            [('foo_i0_j1', {'i': 0, 'j': 1}),
             ('foo_i1_j1', {'i': 1, 'j': 1})]
        )

    def test_name_fail_bare_value(self):
        """Test foo<0,j> fails."""
        # It should be foo<i=0,j>.
        self.assertRaises(ParamExpandError,
                          self.name_expander.expand, 'foo<0,j>')

    def test_name_fail_undefined_param(self):
        """Test that an undefined parameter gets failed."""
        # m is not defined.
        self.assertRaises(ParamExpandError,
                          self.name_expander.expand, 'foo<m,j>')

    def test_name_fail_param_value_too_high(self):
        """Test that an out-of-range parameter gets failed."""
        # i stops at 3.
        self.assertRaises(ParamExpandError,
                          self.name_expander.expand, 'foo<i=4,j>')

    def test_name_multiple(self):
        """Test expansion of two names, with one and two parameters."""
        self.assertEqual(
            self.name_expander.expand('foo<i>, bar<i,j>'),
            [('foo_i0', {'i': 0}),
             ('foo_i1', {'i': 1}),
             ('bar_i0_j0', {'i': 0, 'j': 0}),
             ('bar_i0_j1', {'i': 0, 'j': 1}),
             ('bar_i0_j2', {'i': 0, 'j': 2}),
             ('bar_i1_j0', {'i': 1, 'j': 0}),
             ('bar_i1_j1', {'i': 1, 'j': 1}),
             ('bar_i1_j2', {'i': 1, 'j': 2})]
        )

    def test_graph_expand_1(self):
        """Test graph expansion with two parameters each side of an arrow."""
        self.assertEqual(
            self.graph_expander.expand("bar<i,j>=>baz<i,j>"),
            set(["bar_i0_j1=>baz_i0_j1",
                 "bar_i1_j2=>baz_i1_j2",
                 "bar_i0_j2=>baz_i0_j2",
                 "bar_i1_j1=>baz_i1_j1",
                 "bar_i1_j0=>baz_i1_j0",
                 "bar_i0_j0=>baz_i0_j0"])
        )

    def test_graph_expand_2(self):
        """Test graph expansion to 'branch and merge' a workflow."""
        self.assertEqual(
            self.graph_expander.expand("pre=>bar<i>=>baz<i,j>=>post"),
            set(["pre=>bar_i0=>baz_i0_j1=>post",
                 "pre=>bar_i1=>baz_i1_j2=>post",
                 "pre=>bar_i0=>baz_i0_j2=>post",
                 "pre=>bar_i1=>baz_i1_j1=>post",
                 "pre=>bar_i1=>baz_i1_j0=>post",
                 "pre=>bar_i0=>baz_i0_j0=>post"])
        )

    def test_graph_expand_3(self):
        """Test graph expansion -ve integers."""
        self.assertEqual(
            self.graph_expander.expand("bar<a>"),
            set(["bar_a-1", "bar_a-3"]))

    def test_graph_expand_offset_1(self):
        """Test graph expansion with a -ve offset."""
        self.assertEqual(
            self.graph_expander.expand("bar<i-1,j>=>baz<i,j>"),
            set(["baz_i0_j0",
                 "baz_i0_j1",
                 "baz_i0_j2",
                 "bar_i0_j0=>baz_i1_j0",
                 "bar_i0_j1=>baz_i1_j1",
                 "bar_i0_j2=>baz_i1_j2"])
        )

    def test_graph_expand_offset_2(self):
        """Test graph expansion with a +ve offset."""
        self.assertEqual(
            self.graph_expander.expand("baz<i>=>baz<i+1>"),
            set(["baz_i0=>baz_i1"])
        )

    def test_graph_expand_specific(self):
        """Test graph expansion with a specific value."""
        self.assertEqual(
            self.graph_expander.expand("bar<i=1,j>=>baz<i,j>"),
            set(["bar_i1_j0=>baz_i0_j0",
                 "bar_i1_j1=>baz_i0_j1",
                 "bar_i1_j2=>baz_i0_j2",
                 "bar_i1_j0=>baz_i1_j0",
                 "bar_i1_j1=>baz_i1_j1",
                 "bar_i1_j2=>baz_i1_j2"])
        )

    def test_graph_fail_bare_value(self):
        """Test that a bare parameter value fails in the graph."""
        self.assertRaises(ParamExpandError,
                          self.graph_expander.expand, 'foo<0,j>=>bar<i,j>')

    def test_graph_fail_undefined_param(self):
        """Test that an undefined parameter value fails in the graph."""
        self.assertRaises(ParamExpandError,
                          self.graph_expander.expand, 'foo<m,j>=>bar<i,j>')

    def test_graph_fail_param_value_too_high(self):
        """Test that an out-of-range parameter value fails in the graph."""
        self.assertRaises(ParamExpandError,
                          self.graph_expander.expand, 'foo<i=4,j><i,j>')

    def test_template_fail_missing_param(self):
        """Test a template string specifying a non-existent parameter."""
        self.assertRaises(
            ParamExpandError, self.name_expander.expand, 'foo<k>')
        self.assertRaises(
            ParamExpandError, self.graph_expander.expand, 'foo<k>')


if __name__ == "__main__":
    unittest.main()

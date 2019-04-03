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

from cylc.exceptions import GraphParseError, ParamExpandError
from cylc.graph_parser import GraphParser


class TestGraphParser(unittest.TestCase):
    """Unit tests for the GraphParser class."""

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
        with self.assertRaises(ParamExpandError):
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

    def test_line_continuation(self):
        """Test syntax-driven line continuation."""
        graph1 = "a => b => c"
        graph2 = """a =>
 b => c"""
        graph3 = """a => b
 => c"""
        gp1 = GraphParser()
        gp1.parse_graph(graph1)
        gp2 = GraphParser()
        gp2.parse_graph(graph2)
        gp3 = GraphParser()
        gp3.parse_graph(graph3)
        res = {
            'a': {'': ([], False)},
            'c': {'b:succeed': (['b:succeed'], False)},
            'b': {'a:succeed': (['a:succeed'], False)}
        }
        self.assertEqual(gp1.triggers, res)
        self.assertEqual(gp1.triggers, gp2.triggers)
        self.assertEqual(gp1.triggers, gp3.triggers)
        graph = """foo => bar
            a => b =>"""
        gp = GraphParser()
        self.assertRaises(GraphParseError, gp.parse_graph, graph)
        graph = """ => a => b
            foo => bar"""
        gp = GraphParser()
        self.assertRaises(GraphParseError, gp.parse_graph, graph)

    def test_def_trigger(self):
        """Test default trigger is :succeed."""
        gp1 = GraphParser()
        gp1.parse_graph("foo => bar")
        gp2 = GraphParser()
        gp2.parse_graph("foo:succeed => bar")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_finish_trigger(self):
        """Test finish trigger expansion."""
        gp1 = GraphParser()
        gp1.parse_graph("foo:finish => bar")
        gp2 = GraphParser()
        gp2.parse_graph("(foo:succeed | foo:fail) => bar")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_all_to_all(self):
        """Test family all-to-all semantics."""
        fam_map = {'FAM': ['m1', 'm2'], 'BAM': ['b1', 'b2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:succeed-all => BAM")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("""
            (m1 & m2) => b1
            (m1 & m2) => b2""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_one_to_all(self):
        """Test family one-to-all semantics."""
        fam_map = {'FAM': ['m1', 'm2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("pre => FAM")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("""
            pre => m1
            pre => m2
            """)
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_all_to_one(self):
        """Test family all-to-one semantics."""
        fam_map = {'FAM': ['m1', 'm2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:succeed-all => post")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("(m1 & m2) => post")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_any_to_one(self):
        """Test family any-to-one semantics."""
        fam_map = {'FAM': ['m1', 'm2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:succeed-any => post")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("(m1 | m2) => post")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_any_to_all(self):
        """Test family any-to-all semantics."""
        fam_map = {'FAM': ['m1', 'm2'], 'BAM': ['b1', 'b2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:fail-any => BAM")

        gp2 = GraphParser(fam_map)
        gp2.parse_graph("""
            (m1:fail | m2:fail) => b1
            (m1:fail | m2:fail) => b2""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_finish(self):
        """Test family finish semantics."""
        fam_map = {'FAM': ['m1', 'm2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:finish-all => post")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("""
            ((m1:succeed | m1:fail) & (m2:succeed | m2:fail)) => post""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_parameter_expand(self):
        """Test graph parameter expansion."""
        fam_map = {
            'FAM_m0': ['fa_m0', 'fb_m0'],
            'FAM_m1': ['fa_m1', 'fb_m1'],
        }
        params = {'m': ['0', '1'], 'n': ['0', '1']}
        templates = {'m': '_m%(m)s', 'n': '_n%(n)s'}
        gp1 = GraphParser(fam_map, (params, templates))
        gp1.parse_graph("""
            pre => foo<m,n> => bar<n>
            bar<n=0> => baz  # specific case
            bar<n-1> => bar<n>  # inter-chunk
            """)
        gp2 = GraphParser()
        gp2.parse_graph("""
            pre => foo_m0_n0 => bar_n0
            pre => foo_m0_n1 => bar_n1
            pre => foo_m1_n0 => bar_n0
            pre => foo_m1_n1 => bar_n1
            bar_n0 => baz
            bar_n0 => bar_n1
            """)
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_parameter_specific(self):
        """Test graph parameter expansion with a specific value."""
        params = {'i': ['0', '1'], 'j': ['0', '1', '2']}
        templates = {'i': '_i%(i)s', 'j': '_j%(j)s'}
        gp1 = GraphParser(family_map=None, parameters=(params, templates))
        gp1.parse_graph("bar<i-1,j> => baz<i,j>\nfoo<i=1,j> => qux")
        gp2 = GraphParser()
        gp2.parse_graph("""
           baz_i0_j0
           baz_i0_j1
           baz_i0_j2
           foo_i1_j0 => qux
           foo_i1_j1 => qux
           foo_i1_j2 => qux
           bar_i0_j0 => baz_i1_j0
           bar_i0_j1 => baz_i1_j1
           bar_i0_j2 => baz_i1_j2""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_parameter_offset(self):
        """Test graph parameter expansion with an offset."""
        params = {'i': ['0', '1'], 'j': ['0', '1', '2']}
        templates = {'i': '_i%(i)s', 'j': '_j%(j)s'}
        gp1 = GraphParser(family_map=None, parameters=(params, templates))
        gp1.parse_graph("bar<i-1,j> => baz<i,j>")
        gp2 = GraphParser()
        gp2.parse_graph("""
           baz_i0_j0
           baz_i0_j1
           baz_i0_j2
           bar_i0_j0 => baz_i1_j0
           bar_i0_j1 => baz_i1_j1
           bar_i0_j2 => baz_i1_j2""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_conditional(self):
        """Test generation of conditional triggers."""
        gp1 = GraphParser()
        gp1.parse_graph("(foo:start | bar) => baz")
        res = {
            'baz': {
                '(foo:start|bar:succeed)': (
                    ['foo:start', 'bar:succeed'], False)
            },
            'foo': {
                '': ([], False)
            },
            'bar': {
                '': ([], False)
            }
        }
        self.assertEqual(gp1.triggers, res)

    def test_repeat_trigger(self):
        """Test that repeating a trigger has no effect."""
        gp1 = GraphParser()
        gp2 = GraphParser()
        gp1.parse_graph("foo => bar")
        gp2.parse_graph("""
            foo => bar
            foo => bar""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_chain_stripping(self):
        """Test that trigger type is stripped off right-side nodes."""
        gp1 = GraphParser()
        gp1.parse_graph("""
        bar
        foo => bar:succeed => baz""")
        gp2 = GraphParser()
        gp2.parse_graph("""
            foo => bar
            bar:succeed => baz""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_double_oper(self):
        """Test that illegal forms of the logical operators are detected."""
        graph = "foo && bar => baz"
        gp = GraphParser()
        self.assertRaises(GraphParseError, gp.parse_graph, graph)
        graph = "foo || bar => baz"
        gp = GraphParser()
        self.assertRaises(GraphParseError, gp.parse_graph, graph)

    def test_bad_node_syntax(self):
        """Test that badly formatted graph nodes are detected.

        The correct format is:
          NAME(<PARAMS>)([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE)")
        """
        params = {'m': ['0', '1'], 'n': ['0', '1']}
        templates = {'m': '_m%(m)s', 'n': '_n%(n)s'}
        gp = GraphParser(parameters=(params, templates))
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo[-P1Y]<m,n> => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo:fail<m,n> => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo:fail[-P1Y] => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo[-P1Y]:fail<m,n> => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo[-P1Y]<m,n>:fail => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo<m,n>:fail[-P1Y] => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo:fail<m,n>[-P1Y] => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "<m,n>:fail[-P1Y] => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "[-P1Y]<m,n> => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "[-P1Y]<m,n>:fail => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "bar => foo:fail<m,n>[-P1Y]")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo[-P1Y]baz => bar")

    def test_spaces_between_tasks_fails(self):
        """Test that <task> <task> is rejected (i.e. no & or | in between)"""
        gp = GraphParser()
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo bar=> baz")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo&bar=> ba z")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo 123=> bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo - 123 baz=> bar")

    def test_spaces_between_parameters_fails(self):
        """Test that <param param> are rejected (i.e. no comma)"""
        gp = GraphParser()
        self.assertRaises(
            GraphParseError, gp.parse_graph, "<foo bar> => baz")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "<foo=a _bar> => baz")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "<foo=a_ bar> => baz")

    @classmethod
    def test_spaces_between_parameters_passes(cls):
        """Test that <param-1> works, with spaces around the -+ signs"""
        params = {'m': ['0', '1', '2']}
        templates = {'m': '_m%(m)s'}
        gp = GraphParser(parameters=(params, templates))
        gp.parse_graph("<m- 1> => <m>")
        gp.parse_graph("<m -1> => <m>")
        gp.parse_graph("<m - 1> => <m>")
        gp.parse_graph("<m+ 1> => <m>")
        gp.parse_graph("<m +1> => <m>")
        gp.parse_graph("<m + 1> => <m>")

    def test_spaces_in_trigger_fails(self):
        """Test that 'task:a- b' are rejected"""
        gp = GraphParser()
        self.assertRaises(
            GraphParseError, gp.parse_graph, "FOO:custom -trigger => baz")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "FOO:custom- trigger => baz")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "FOO:custom - trigger => baz")


if __name__ == "__main__":
    unittest.main()

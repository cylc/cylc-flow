# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
import pytest
from pytest import param

from cylc.flow.exceptions import ParamExpandError
from cylc.flow.param_expand import NameExpander, GraphExpander


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
            set(["bar_i-32768_j0=>baz_i0_j0",
                 "bar_i-32768_j1=>baz_i0_j1",
                 "bar_i-32768_j2=>baz_i0_j2",
                 "bar_i0_j0=>baz_i1_j0",
                 "bar_i0_j1=>baz_i1_j1",
                 "bar_i0_j2=>baz_i1_j2"])
        )

    def test_graph_expand_offset_2(self):
        """Test graph expansion with a +ve offset."""
        self.assertEqual(
            self.graph_expander.expand("baz<i>=>baz<i+1>"),
            set(["baz_i0=>baz_i1",
                 "baz_i1=>baz_i-32768"])
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

    @staticmethod
    def _param_expand_params():
        """Test data for test_parameter_graph_mixing_offset_and_conditional.

            params_map, templates, expanded_str, expanded_values
            params_map     : map of parameters used in the graph expression
            templates      : parameters template
            expanded_str   : graph string, using params/template
            expanded_values: values expected to exist after params expanded
        """
        return (
            # original case from #2608
            (
                {'m': ["cat", "dog"]},
                {'m': '_%(m)s'},
                "foo<m-1> & baz => foo<m>",
                [
                    'foo_-32768 & baz => foo_cat',
                    'foo_cat & baz => foo_dog'
                ]
            ),
            # cases from comments from #2608
            # see cylc/cylc-flow/pull/3452#issuecomment-670782800
            (
                # single element, so bar<m-1> does not exist
                {'m': ["cat"]},
                {'m': '_%(m)s'},
                "foo & bar<m-1> & baz => qux",
                [
                    "foo & bar_-32768 & baz => qux"
                ]
            ),
            # cases from comments from #2608
            # see cylc/cylc-flow/pull/3452#issuecomment-670776749
            (
                {'m': ["1", "2"]},
                {'m': '_%(m)s'},
                "foo<m-1> => bar<m> => baz",
                [
                    "foo_-32768 => bar_1 => baz",
                    "foo_1 => bar_2 => baz"
                ]
            ),
            # cases from comments from #2608
            # see cylc/cylc-flow/pull/3452#discussion_r430967867
            (
                {'m': ["cat", "dog"]},
                {'m': '_%(m)s'},
                "baz & foo<m-1> & pub => foo<m>",
                [
                    "baz & foo_-32768 & pub => foo_cat",
                    "baz & foo_cat & pub => foo_dog"
                ]
            ),
            (
                {'m': ["cat", "dog"]},
                {'m': '_%(m)s'},
                "bar & foo<m-1> & pub<m-1> & qux => foo<m>",
                [
                    "bar & foo_-32768 & pub_-32768 & qux => foo_cat",
                    "bar & foo_cat & pub_cat & qux => foo_dog"
                ]
            ),
            # GraphParser strips spaces!
            (
                {'m': ["cat"]},
                {'m': '_%(m)s'},
                "foo&bar<m-1>&baz=>qux",
                [
                    "foo&bar_-32768&baz=>qux"
                ]
            ),
            (
                {'m': ["cat", "dog"]},
                {'m': '_%(m)s'},
                "foo&bar<m-1>&baz=>qux",
                [
                    "foo&bar_-32768&baz=>qux",
                    "foo&bar_cat&baz=>qux"
                ]
            ),
            # must support & and | in graph expressions
            (
                {'m': ["cat", "dog"]},
                {'m': '_%(m)s'},
                "foo|bar<m-1>|baz=>qux",
                [
                    "foo|bar_-32768|baz=>qux",
                    "foo|bar_cat|baz=>qux"
                ]
            ),
            (
                {'m': ["cat", "dog"]},
                {'m': '_%(m)s'},
                "foo&bar<m-1>|baz=>qux",
                [
                    "foo&bar_-32768|baz=>qux",
                    "foo&bar_cat|baz=>qux"
                ]
            ),
            (
                {'m': ["cat", "dog"]},
                {'m': '_%(m)s'},
                "foo&bar<m-1>|baz=>qux",
                [
                    "foo&bar_-32768|baz=>qux",
                    "foo&bar_cat|baz=>qux"
                ]
            ),
            (
                {'m': ["cat"]},
                {'m': '_%(m)s'},
                "foo => bar<m-1> => baz",
                [
                    "foo=>bar_-32768=>baz"
                ]
            )
        )

    def test_parameter_graph_mixing_offset_and_conditional(self):
        """Test for bug reported in issue #2608 on GitHub."""
        for test_case in self._param_expand_params():
            params_map, templates, expanded_str, expanded_values = \
                test_case
            graph_expander = GraphExpander((params_map, templates))
            # Ignore white spaces.
            expanded = [expanded.replace(' ', '') for expanded in
                        graph_expander.expand(expanded_str)]
            self.assertEqual(
                len(expanded_values),
                len(expanded),
                f"Invalid length for expected {expanded_values} and "
                f"{expanded}")
            # When testing, we don't really care for white spaces,as they
            # are removed in the GraphParser anyway. That's why we have
            # ''.replace(' ', '').
            for expected in expanded_values:
                self.assertTrue(
                    expected.replace(' ', '') in expanded,
                    f"Expected value {expected.replace(' ', '')} "
                    f"not in {expanded}")


class myParam():
    def __init__(
        self, raw_str,
        parameter_values=None, templates=None, raises=None,
        id_=None,
        expect=None,
    ):
        """Ease of reading wrapper for pytest.param

        Args:
            expect:
                Output of expand_parent_params()
            raw_str:
                The parent_params input string.
            parameter_values
        """
        parameter_values = parameter_values if parameter_values else {}
        templates = templates if templates else {}
        self.raises = raises
        self.expect = expect
        self.raw_str = raw_str
        self.parameter_values = parameter_values
        self.templates = templates
        self.parameters = ((parameter_values, templates))
        self.name_expander = NameExpander(self.parameters)
        self.id_ = 'raises:' + id_ if raises else id_

    def get(self):
        return param(self, id=self.id_)


@pytest.mark.parametrize(
    "param",
    (
        myParam(
            expect=(None, 'no_params_here'),
            raw_str='no_params_here',
            id_='basic'
        ).get(),
        myParam(
            expect=({'bar': 1}, 'bar1'),
            raw_str='<bar>',
            parameter_values={'bar': 1},
            templates={'bar': 'bar%(bar)s'},
            id_='one-valid_-param'
        ).get(),
        myParam(
            expect=({'bar': 1}, 'foo_bar1_baz'),
            raw_str='foo<bar>baz',
            parameter_values={'bar': 1},
            templates={'bar': '_bar%(bar)s_'},
            id_='one-valid_-param'
        ).get(),
        myParam(
            raw_str='foo<bar>baz',
            parameter_values={'qux': 2},
            templates={'bar': '_bar%(bar)s_'},
            raises=(ParamExpandError, 'parameter \'bar\' undefined'),
            id_='one-invalid_-param'
        ).get(),
        myParam(
            expect=({'bar': 1, 'baz': 42}, 'foo_bar1_baz42'),
            raw_str='foo<bar, baz>',
            parameter_values={'bar': 1, 'baz': 42},
            templates={'bar': '_bar%(bar)s', 'baz': '_baz%(baz)s'},
            id_='two-valid_-param'
        ).get(),
        myParam(
            expect=({'bar': 1, 'baz': 42}, 'foo_bar1qux_baz42'),
            raw_str='foo<bar>qux<baz>',
            parameter_values={'bar': 1, 'baz': 42},
            templates={'bar': '_bar%(bar)s', 'baz': '_baz%(baz)s'},
            id_='two-valid_-param-sep-brackets',
        ).get(),
        myParam(
            raw_str='foo<bar-1>baz',
            raises=(ParamExpandError, '^parameter offsets illegal here'),
            id_='offsets-illegal'
        ).get(),
        myParam(
            expect=({'bar': 1}, 'foo_bar1_baz'),
            raw_str='foo<bar=1>baz',
            parameter_values={'bar': [1, 2]},
            templates={'bar': '_bar%(bar)s_'},
            id_='value-set'
        ).get(),
        myParam(
            raw_str='foo<bar=3>baz',
            parameter_values={'bar': [1, 2]},
            raises=(ParamExpandError, '^illegal'),
            id_='illegal-value'
        ).get(),
        myParam(
            expect=({'bar': 1}, 'foo_bar1_baz'),
            raw_str='foo<bar=3>baz',
            raises=(ParamExpandError, '^parameter \'bar\' undefined'),
            id_='parameter-undefined'
        ).get(),
    )
)
def test_expand_parent_params(param):
    if not param.raises:
        # Good Path tests:
        result = param.name_expander.expand_parent_params(
            param.raw_str, param.parameter_values, 'Errortext')
        assert result == param.expect
    else:
        # Bad path tests:
        with pytest.raises(param.raises[0], match=param.raises[1]):
            param.name_expander.expand_parent_params(
                param.raw_str, param.parameter_values, 'Errortext')

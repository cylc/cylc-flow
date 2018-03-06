#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
"""Parameter expansion for runtime namespace names and graph strings.

Uses recursion to achieve nested looping over any number of parameters.  In its
simplest form (without allowing for parameter offsets and specific values, and
with input already expressed as a string template) the method looks like this:

#------------------------------------------------------------------------------
def expand(template, params, results, values=None):
    '''Recursive parameter expansion.

    template: e.g. "foo_m(m)s=>bar_m%(m)s_n%(n)s".
    results: output list of expanded strings.
    params: list of parameter (name, max-value) tuples.
    '''
    if values is None:
        values = {}
    if not params:
        results.add(template % values)
    else:
        param = params[0]
        for value in range(param[1]):
            values[param[0]] = value
            expand(template, params[1:], results, values)
#------------------------------------------------------------------------------
if __name__ == "__main__":
    results = []
    expand(
        "foo_m%(m)s=>bar_m%(m)s_n%(n)s",
        results,
        [('m', 2), ('n', 3)]
    )
    for result in results:
        print result

foo_m0=>bar_m0_n0
foo_m0=>bar_m0_n1
foo_m0=>bar_m0_n2
foo_m1=>bar_m1_n0
foo_m1=>bar_m1_n1
foo_m1=>bar_m1_n2
#------------------------------------------------------------------------------
"""

import re
import unittest

from cylc.task_id import TaskID
from parsec.OrderedDict import OrderedDictWithDefaults

# To split runtime heading name lists.
REC_NAMES = re.compile(r'(?:[^,<]|\<[^>]*\>)+')
# To extract (e.g.) 'name', 'the, quick, brown', and 'other' from
#   'name<the, quick, brown>other' (other is used for clock-offsets).
REC_P_ALL = re.compile(r"(%s)?(?:<(.*?)>)?(.+)?" % TaskID.NAME_RE)
# To extract all parameter lists e.g. 'm,n,o' (from '<m,n,o>').
REC_P_GROUP = re.compile(r"<(.*?)>")
# To extract parameter name and optional offset or value e.g. 'm-1'.
REC_P_OFFS = re.compile(
    r'(\w+)\s*([\-\+]\s*\d+|=\s*%s)?' % TaskID.NAME_SUFFIX_RE)


def item_in_iterable(item, itt):
    """Return True if item is in itt, by string or int comparison.

    Items may be general strings, or strings of zero-padded integers.
    """
    if item in itt:
        return True
    try:
        int(item)
    except ValueError:
        return False
    return int(item) in (int(i) for i in itt)


class ParamExpandError(Exception):
    """For parameter expansion errors."""
    pass


class NameExpander(object):
    """Handle parameter expansion in runtime namespace headings."""

    def __init__(self, parameters):
        """Initialize the parameterized task name expander.

        parameters is:
            ({param_name: [param_values],  # list of strings
             {param_name: param_template}) # e.g. "_m%(m)s"
        """
        self.param_cfg, self.param_tmpl_cfg = parameters

    def expand(self, runtime_heading):
        """Expand runtime namespace names for a subset of suite parameters.

        Input runtime_heading is a string that may contain comma-separated
        parameterized namespace names, e.g. for "foo<m,n>, bar<m,n>".

        Unlike GraphExpander this does not support offsets like "foo<m-1,n>",
        but it does support specific parameter values like "foo<m=0,n>".

        Returns a list of tuples, each with an expanded name and its parameter
        values (to be passed to the corresponding tasks), e.g.:
            [('foo_i0_j0', {i:'0', j:'0'}),
             ('foo_i0_j1', {i:'0', j:'1'}),
             ('foo_i1_j0', {i:'1', j:'0'}),
             ('foo_i1_j1', {i:'1', j:'1'})]
        """
        # Create a string template and values to pass to the expansion method.
        results = []
        for name in REC_NAMES.findall(runtime_heading):
            tmpl = ''
            spec_vals = {}
            used_params = []
            while name:
                head, p_list_str, tail = REC_P_ALL.match(name.strip()).groups()
                if not p_list_str:
                    break
                if head:
                    tmpl += head
                # Get the subset of parameters used in this case.
                for item in (i.strip() for i in p_list_str.split(',')):
                    pname, sval = REC_P_OFFS.match(item.strip()).groups()
                    if not self.param_cfg.get(pname, None):
                        raise ParamExpandError(
                            "ERROR, parameter %s is not defined in %s" % (
                                pname, runtime_heading))
                    if sval:
                        if sval.startswith('+') or sval.startswith('-'):
                            raise ParamExpandError(
                                "ERROR, parameter index offsets are not"
                                " supported in name expansion: %s%s" % (
                                    pname, sval))
                        elif sval.startswith('='):
                            # Check that specific parameter values exist.
                            val = sval[1:].strip()
                            # Pad integer values here.
                            try:
                                nval = int(val)
                            except ValueError:
                                nval = val
                            if not item_in_iterable(
                                    nval, self.param_cfg[pname]):
                                raise ParamExpandError(
                                    "ERROR, parameter %s out of range: %s" % (
                                        pname, p_list_str))
                            spec_vals[pname] = nval
                    else:
                        used_params.append((pname, self.param_cfg[pname]))
                    tmpl += self.param_tmpl_cfg[pname]
                if tail:
                    name = tail
                else:
                    name = ''
            if tmpl:
                tmpl += name
                self._expand_name(results, tmpl, used_params, spec_vals)
            else:
                results.append((name.strip(), {}))
        return results

    def _expand_name(self, results, tmpl, params, spec_vals=None):
        """Recursively expand tmpl for any number of parameters.

        tmpl is a string template, e.g. 'foo_m%(m)s_n%(n)s' for two
            parameters m and n.
        params is a list of tuples (name, max-val) for each parameter
            to be looped over.
        spec_vals is a map of values for parameters that are not to be looped
            over because they've been assigned a specific value.

        E.g. for "foo<m=0,n>" tmpl is "foo_m%(m)s_n%(n)s", params is
        [('n', 2)], and spec_values {'m': 0}.

        results contains the expanded names and corresponding parameter values,
        as described above in the calling method.
        """
        if spec_vals is None:
            spec_vals = {}
        if not params:
            # Inner loop.
            current_values = dict(spec_vals)
            try:
                results.append((tmpl % current_values, current_values))
            except KeyError as exc:
                raise ParamExpandError('ERROR: parameter %s is not '
                                       'defined.' % str(exc.args[0]))
        else:
            for param_val in params[0][1]:
                spec_vals[params[0][0]] = param_val
                self._expand_name(results, tmpl, params[1:], spec_vals)

    def expand_parent_params(self, parent, param_values, origin):
        """Replace parameters with specific values in inherited parent names.

        If a value is NOT specified, e.g.:
            inherit = parent<m>
        then it must be given in param_values (as defined by expansion of the
        enclosing namespace name).

        If a value IS specified, e.g.:
            inherit = parent<m=3>
        then it must be a legal value for that parameter.

        """
        head, p_list_str, tail = REC_P_ALL.match(parent).groups()
        if not p_list_str:
            return head
        used = {}
        for item in (i.strip() for i in p_list_str.split(',')):
            if '-' in item or '+' in item:
                raise ParamExpandError(
                    "ERROR, parameter offsets illegal here: '%s'" % origin)
            elif '=' in item:
                # Specific value given.
                pname, pval = re.split('\s*=\s*', item)
                try:
                    pval = int(pval)
                except ValueError:
                    pass
                if pname not in self.param_cfg:
                    raise ParamExpandError(
                        "ERROR, parameter '%s' undefined in '%s'" % (
                            pname, origin))
                elif pval not in self.param_cfg[pname]:
                    raise ParamExpandError(
                        "ERROR, illegal value '%s=%s' in '%s'" % (
                            pname, pval, origin))
                used[pname] = pval
            else:
                # Non-specific; value must be supplied in param_values.
                try:
                    used[item] = param_values[item]
                except KeyError:
                    raise ParamExpandError(
                        "ERROR, parameter '%s' undefined in '%s'" % (
                            item, origin))
        if head:
            tmpl = head
        else:
            tmpl = ''
        for pname in used:
            tmpl += self.param_tmpl_cfg[pname]
        if tail:
            tmpl += tail
        return tmpl % used


class GraphExpander(object):
    """Handle parameter expansion of graph string lines."""

    _REMOVE = -32768
    _REMOVE_REC = re.compile(
        r'(?:^|\s*=>).*' + str(_REMOVE) + r'.*?(?:$|=>\s*?)')

    def __init__(self, parameters):
        """Initialize the parameterized task name expander.

        parameters is:
            ({param_name: [param_values],  # list of strings
             {param_name: param_template}) # e.g. "_m%(m)s"
        """
        try:
            self.param_cfg, self.param_tmpl_cfg = parameters
        except (TypeError, ValueError):
            self.param_cfg, self.param_tmpl_cfg = ({}, {})

    def expand(self, line):
        """Expand a graph line for subset of suite parameters.

        Input line is a string that may contain multiple parameterized node
        names, e.g. "pre=>init<m>=>sim<m,n>=>post<m,n>=>done".

        Unlike NameExpander this supports offsets like "foo<m-1,n>", which
        means (because the parameter substitutions have to be computed on the
        fly) we have shift creation of the expansion string template into the
        inner loop of the recursive expansion function.

        Returns a set containing lines expanded for all used parameters, e.g.
        for "foo=>bar<m,n>" with m=2 and n=2 the result would be:
            set([foo=>bar_m0_n0,
                 foo=>bar_m0_n1,
                 foo=>bar_m1_n0,
                 foo=>bar_m1_n1])

        Specific parameter values can be singled out like this:
            "sim<m=0,n>=>sim<m,n>"
        Offset (negative only) values can be specified like this:
            "sim<m-1,n>=>sim<m,n>"
        (Here the offset node must be the first in a line, and if m-1 evaluates
        to less than 0 the node will be removed to leave just "sim<m,n>").
        """
        line_set = set()
        used_pnames = []
        for p_group in set(REC_P_GROUP.findall(line)):
            for item in p_group.split(','):
                pname, offs = REC_P_OFFS.match(item).groups()
                if not self.param_cfg.get(pname, None):
                    raise ParamExpandError(
                        "ERROR, parameter %s is not defined in <%s>: %s" % (
                            pname, p_group, line))
                if offs and offs.startswith('='):
                    # Check that specific parameter values exist.
                    val = offs[1:]
                    try:
                        nval = int(val)
                    except ValueError:
                        nval = val
                    if not item_in_iterable(nval, self.param_cfg[pname]):
                        raise ParamExpandError(
                            "ERROR, parameter %s out of range: %s" % (
                                pname, p_group))
                if pname not in used_pnames:
                    used_pnames.append(pname)
        used_params = [(p, self.param_cfg[p]) for p in used_pnames]
        self._expand_graph(line, dict(used_params), used_params, line_set)
        return line_set

    def _expand_graph(self, line, all_params,
                      param_list, line_set, values=None):
        """Expand line into line_set for any number of parameters.

        line is a graph string line as described above in the calling method.
        param_list is a list of tuples (name, max-val) for each parameter.
        results is a set to hold each expanded line.
        """
        if values is None:
            values = {}
        if not param_list:
            # Inner loop.
            for p_group in set(REC_P_GROUP.findall(line)):
                # Parameters must be expanded in the order found.
                param_values = OrderedDictWithDefaults()
                tmpl = ''
                for item in p_group.split(','):
                    pname, offs = REC_P_OFFS.match(item).groups()
                    if offs is None:
                        param_values[pname] = values[pname]
                    elif offs.startswith('='):
                        # Specific value.
                        try:
                            # Template may require an integer
                            param_values[pname] = int(offs[1:])
                        except ValueError:
                            param_values[pname] = offs[1:]
                    else:
                        # Index offset.
                        plist = all_params[pname]
                        cur_idx = plist.index(values[pname])
                        off_idx = cur_idx + int(offs)
                        if 0 <= off_idx < len(plist):
                            offval = plist[off_idx]
                        else:
                            offval = self._REMOVE
                        param_values[pname] = offval
                for pname in param_values:
                    tmpl += self.param_tmpl_cfg[pname]
                try:
                    repl = tmpl % param_values
                except KeyError as exc:
                    raise ParamExpandError('ERROR: parameter %s is not '
                                           'defined.' % str(exc.args[0]))
                line = line.replace('<' + p_group + '>', repl)
                # Remove out-of-range nodes
                line = self._REMOVE_REC.sub('', line)
            if line:
                line_set.add(line)
        else:
            # Recurse through index ranges.
            for param_val in param_list[0][1]:
                values[param_list[0][0]] = param_val
                self._expand_graph(line, all_params,
                                   param_list[1:], line_set, values)


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

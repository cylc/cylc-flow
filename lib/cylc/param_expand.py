#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

import re
import unittest
from copy import copy
from task_id import TaskID

"""Parameter expansion for runtime namespace names and graph strings.

Uses recursion to achieve nested looping over any number of parameters.  In its
simplest form (without allowing for parameter offsets and specific values, and
with input already expressed as a string template) the method looks like this:

#------------------------------------------------------------------------------
# def expand(template, params, results, values=None):
#     '''Recursive parameter expansion.
#
#     template: e.g. "foo_m(m)s => bar_m%(m)s_n%(n)s".
#     results: output list of expanded strings.
#     params: list of parameter (name, max-value) tuples.
#     '''
#     if values is None:
#         values = {}
#     if not params:
#         results.add(template % values)
#     else:
#         param = params[0]
#         for value in range(param[1]):
#             values[param[0]] = value
#             expand(template, params[1:], results, values)
#
# if __name__ == "__main__":
#     results = []
#     expand(
#         "foo_m%(m)s => bar_m%(m)s_n%(n)s",
#         results,
#         [('m', 2), ('n', 3)]
#     )
#     for result in results:
#         print result
#
# foo_m0 => bar_m0_n0
# foo_m0 => bar_m0_n1
# foo_m0 => bar_m0_n2
# foo_m1 => bar_m1_n0
# foo_m1 => bar_m1_n1
# foo_m1 => bar_m1_n2
#------------------------------------------------------------------------------
"""


class ParamExpandError(Exception):
    """For parameter expansion errors."""
    pass


class NameExpander(object):
    """Handle parameter expansion in runtime namespace headings."""

    # To split heading name lists.
    REC_NAMES = re.compile(r'(?:[^,<]|\<[^>]*\>)+')
    # Extract 'name' and '<parameters>' from 'name<parameters>'.
    REC_P_NAME = re.compile(r"(%s)(<.*?>)?" % TaskID.NAME_RE)
    # As for offset, but only match specific values e.g. 'm=1'.
    REC_P_SPEC = re.compile(r'(\w+)(?:\s*=\s*([\d]+))?')

    @classmethod
    def replace_params(cls, name, parameters):
        """Replace <m,n,..> in name<m,n,...> with given values."""
        name, p_tmpl = cls.REC_P_NAME.match(name).groups()
        if not p_tmpl:
            # Name is not parameterized.
            return name
        # List of parameter names used in this name: ['m', 'n']
        used_param_names = [i.strip() for i in p_tmpl[1:-1].split(',')]
        # String template: "_m%(m)s_n%(n)s".
        str_template = name + ''.join(
            ["_" + p + "%(" + p + ")s" for p in used_param_names])
        return str_template % parameters

    def __init__(self, suite_parameter_map):
        """Store the suite parameter map."""
        self.suite_parameter_map = suite_parameter_map

    def expand(self, runtime_heading):
        """Expand runtime namespace names for a subset of suite parameters.

        Input runtime_heading is a string that may contain comma-separated
        parameterized namespace names, e.g. for "foo<m,n>, bar<m,n>".

        Unlike GraphExpander this does not support offsets like "foo<m-1,n>",
        but it does support specific parameter values like "foo<m=0,n>".

        Returns a list of tuples, each with an expanded name and its parameter
        values (to be passed to the corresponding tasks), e.g.:
            [(foo_i0_j0, {i:0, j:0}),
             (foo_i0_j1, {i:0, j:1}),
             (foo_i1_j0, {i:1, j:0}),
             (foo_i1_j1, {i:1, j:1})]
        """
        # Create a string template and values to pass to the expansion method.
        expanded = []
        for namespace in self.__class__.REC_NAMES.findall(runtime_heading):
            template = namespace.strip()
            name, p_tmpl = self.__class__.REC_P_NAME.match(template).groups()
            if not p_tmpl:
                # Not parameterized.
                expanded.append((name, {}))
                continue
            # Get the subset of parameters used in this case.
            used_param_names = []
            spec_vals = {}
            for item in p_tmpl[1:-1].split(','):
                pname, sval = self.__class__.REC_P_SPEC.match(
                    item.strip()).groups()
                # Check for bare values like foo<0,j> instead of foo<i=0,j>.
                try:
                    int(pname)
                except ValueError:
                    pass
                else:
                    raise ParamExpandError(
                        "ERROR, write specific parameter values as"
                        " 'foo<i=0,j>' not 'foo<0,j>': %s" % template)
                # Check for use of undefined parameters.
                if pname not in self.suite_parameter_map:
                    raise ParamExpandError("ERROR, parameter %s is not"
                                           " defined: %s" % (pname, template))
                # Check for specific parameter values that are too big.
                if sval:
                    i_sval = int(sval)
                    max_val = self.suite_parameter_map[pname]
                    if i_sval > max_val:
                        raise ParamExpandError(
                            "ERROR, max value of parameter %s is"
                            " %d: %s" % (pname, max_val, template))
                    spec_vals[pname] = i_sval
                else:
                    used_param_names.append(pname)
            used_parameters = [
                (p, self.suite_parameter_map[p]) for p in used_param_names]
            # Creat the string template.  This can be done now because name
            # expansion - unlike graph expansion - doesn't support offsets.
            tmpl = name
            for item in p_tmpl[1:-1].split(','):
                p, _ = self.__class__.REC_P_SPEC.match(item.strip()).groups()
                tmpl += "_" + p + "%(" + p + ")s"
            self._expand_name(tmpl, used_parameters, expanded, spec_vals)
        return expanded

    def _expand_name(self, str_tmpl, param_list, results, spec_vals=None):
        """Expand str_tmpl for any number of parameters.

        str_tmpl is a string template, e.g. 'foo_m%(m)s_n%(n)s' for two
            parameters m and n.
        param_list is a list of tuples (name, max-val) for each parameter
            to be looped over.
        spec_vals is a map of values for parameters that are not to be looped
            over because they've been assigned a specific value.

        E.g. for "foo<m=0,n>" str_tmpl is "foo_m%(m)s_n%(n)s", param_list is
        [('n', 2)], and spec_values {'m': 0}.

        results contains the expanded names and corresponding parameter values,
        as described above in the calling method.
        """
        if spec_vals is None:
            spec_vals = {}
        if not param_list:
            # Inner loop.
            current_values = copy(spec_vals)
            results.append((str_tmpl % current_values, current_values))
        else:
            for param_val in range(param_list[0][1]):
                spec_vals[param_list[0][0]] = param_val
                self._expand_name(str_tmpl, param_list[1:], results, spec_vals)


class GraphExpander(object):
    """Handle parameter expansion of graph string lines."""

    # Extract parameter list 'm,n,o' from '<m,n,o>'.
    REC_P_GROUP = re.compile(r"<(.*?)>")
    # Extract name and optional offset or specific value e.g. 'm-1'.
    REC_P_OFFS = re.compile(r'(\w+)(?:\s*([-+=]\s*[\d]+))?')

    def __init__(self, suite_parameter_map):
        """Store the suite parameter map."""
        self.suite_parameter_map = suite_parameter_map

    def expand(self, line):
        """Expand a graph line for subset of suite parameters.

        Input line is a string that may contain multiple parameterized node
        names, e.g. "pre => init<m> => sim<m,n> => post<m,n> => done".

        Unlike NameExpander this supports offsets like "foo<m-1,n>", which
        means (because the parameter substitutions have to be computed on the
        fly) we have shift creation of the expansion string template into the
        inner loop of the recursive expansion function.

        Returns a set containing lines expanded for all used parameters, e.g.
        for "foo => bar<m,n>" with m=2 and n=2 the result would be:
            set([foo => bar_m0_n0,
                 foo => bar_m0_n1,
                 foo => bar_m1_n0,
                 foo => bar_m1_n1])

        Specific parameter values can be singled out like this:
            "sim<m=0,n> => sim<m,n>"
        Offset (negative only) values can be specified like this:
            "sim<m-1,n> => sim<m,n>"
        (Here the offset node must be the first in a line, and if m-1 evaluates
        to less than 0 the node will be removed to leave just "sim<m,n>").
        """
        line_set = set()
        used_pnames = set()
        for p_group in set(self.__class__.REC_P_GROUP.findall(line)):
            for item in p_group.split(','):
                pname, offs = self.__class__.REC_P_OFFS.match(
                    item.strip()).groups()
                # Check for bare values like foo<0,j> for foo<i=0,j>.
                try:
                    int(pname)
                except ValueError:
                    pass
                else:
                    raise ParamExpandError(
                        "ERROR, write specific parameter values as"
                        " 'foo<i=0,j>' not 'foo<0,j>': %s" % p_group)
                # Check for use of undefined parameters.
                if pname not in self.suite_parameter_map:
                    raise ParamExpandError(
                        "ERROR, parameter %s is not defined: %s" % (
                            pname, p_group))
                if offs:
                    # Check for legal offset values.
                    if offs.startswith('+'):
                        raise ParamExpandError(
                            "ERROR, +ve parameter offsets are not"
                            " supported: %s%s" % (pname, offs))
                    elif offs.startswith('='):
                        # Check for specific parameter values that are too big.
                        if offs:
                            max_val = self.suite_parameter_map[pname]
                            if int(offs[1:]) > max_val:
                                raise ParamExpandError(
                                    "ERROR, max value of parameter %s is"
                                    " %d: %s" % (pname, max_val, p_group))
                used_pnames.add(pname)
        used_params = [(p, self.suite_parameter_map[p]) for p in used_pnames]
        self._expand_graph(line, used_params, line_set)
        return line_set

    def _expand_graph(self, line, param_list, line_set, values=None):
        """Expand line into line_set for any number of parameters.

        line is a graph string line as described above in the calling method.
        param_list is a list of tuples (name, max-val) for each parameter.
        results is a set to hold each expanded line.
        """

        if values is None:
            values = {}
        if not param_list:
            # Inner loop.
            for p_group in set(self.__class__.REC_P_GROUP.findall(line)):
                param_values = {}
                tmpl = ""
                for item in p_group.split(','):
                    pname, offs = self.__class__.REC_P_OFFS.match(
                        item.strip()).groups()
                    if offs is None:
                        param_values[pname] = values[pname]
                    elif offs.startswith('='):
                        # Absolute value (not a relative offs).
                        param_values[pname] = int(offs[1:])
                    else:
                        # Relative offset.
                        offval = values[pname] + int(offs)
                        if offval < 0:
                            offval = "--<REMOVE>--"
                        param_values[pname] = offval
                    tmpl += "_" + pname + "%(" + pname + ")s"
                match = '<' + p_group + '>'
                repl = tmpl % param_values
                line = re.sub(match, repl, line)
                # Remove out-of-range nodes to first arrow.
                line = re.sub('^.*--<REMOVE>--.*?=>\s*?', '', line)
            line_set.add(line.strip())
        else:
            # Recurse through index ranges.
            for param_val in range(0, param_list[0][1]):
                values[param_list[0][0]] = param_val
                self._expand_graph(line, param_list[1:], line_set, values)


class TestParamExpand(unittest.TestCase):
    """Unit tests for the parameter expansion functionality.
    
    Method doc strings are ommitted; the tests should self-explanatory.
    """

    def setUp(self):
        params_map = {'i': 2, 'j': 3, 'k': 2}
        self.name_expander = NameExpander(params_map)
        self.graph_expander = GraphExpander(params_map)

    def test_name_two_params(self):
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
        self.assertEqual(
            self.name_expander.expand('foo<i>, bar<j>'),
            [('foo_i0', {'i': 0}),
             ('foo_i1', {'i': 1}),
             ('bar_j0', {'j': 0}),
             ('bar_j1', {'j': 1}),
             ('bar_j2', {'j': 2})]
        )

    def test_name_specific_val_1(self):
        self.assertEqual(
            self.name_expander.expand('foo<i=0>'),
            [('foo_i0', {'i': 0})]
        )

    def test_name_specific_val_2(self):
        self.assertEqual(
            self.name_expander.expand('foo<i=0,j>'),
            [('foo_i0_j0', {'i': 0, 'j': 0}),
             ('foo_i0_j1', {'i': 0, 'j': 1}),
             ('foo_i0_j2', {'i': 0, 'j': 2})]
        )

    def test_name_specific_val_3(self):
        self.assertEqual(
            self.name_expander.expand('foo<i,j=1>'),
            [('foo_i0_j1', {'i': 0, 'j': 1}),
             ('foo_i1_j1', {'i': 1, 'j': 1})]
        )

    def test_name_fail_bare_value(self):
        """Test foo<0,j> fails, should be foo<i=0,j>."""
        self.assertRaises(ParamExpandError,
                          self.name_expander.expand,
                          'foo<0,j>')

    def test_name_fail_undefined_param(self):
        self.assertRaises(ParamExpandError,
                          self.name_expander.expand,
                          'foo<m,j>')

    def test_name_fail_param_value_too_high(self):
        self.assertRaises(ParamExpandError,
                          self.name_expander.expand,
                          'foo<i=4,j>')

    def test_name_multiple(self):
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
        self.assertEqual(
            self.graph_expander.expand("bar<i,j> => baz<i,j>"),
            set(["bar_i0_j1 => baz_i0_j1",
                 "bar_i1_j2 => baz_i1_j2",
                 "bar_i0_j2 => baz_i0_j2",
                 "bar_i1_j1 => baz_i1_j1",
                 "bar_i1_j0 => baz_i1_j0",
                 "bar_i0_j0 => baz_i0_j0"])
        )

    def test_graph_expand_2(self):
        self.assertEqual(
            self.graph_expander.expand(
                "pre => bar<i> => baz<i,j> => post"),
            set(["pre => bar_i0 => baz_i0_j1 => post",
                 "pre => bar_i1 => baz_i1_j2 => post",
                 "pre => bar_i0 => baz_i0_j2 => post",
                 "pre => bar_i1 => baz_i1_j1 => post",
                 "pre => bar_i1 => baz_i1_j0 => post",
                 "pre => bar_i0 => baz_i0_j0 => post"])
        )

    def test_graph_expand_offset(self):
        self.assertEqual(
            self.graph_expander.expand(
                "bar<i-1,j> => baz<i,j>"),
            set(["baz_i0_j0",
                 "baz_i0_j1",
                 "baz_i0_j2",
                 "bar_i0_j0 => baz_i1_j0",
                 "bar_i0_j1 => baz_i1_j1",
                 "bar_i0_j2 => baz_i1_j2"])
        )

    def test_graph_expand_specific(self):
        self.assertEqual(
            self.graph_expander.expand("bar<i=1,j> => baz<i,j>"),
            set(["bar_i1_j0 => baz_i0_j0",
                 "bar_i1_j1 => baz_i0_j1",
                 "bar_i1_j2 => baz_i0_j2",
                 "bar_i1_j0 => baz_i1_j0",
                 "bar_i1_j1 => baz_i1_j1",
                 "bar_i1_j2 => baz_i1_j2"])
        )

    def test_graph_fail_bare_value(self):
        self.assertRaises(ParamExpandError,
                          self.graph_expander.expand,
                          'foo<0,j> => bar<i,j>')

    def test_graph_fail_undefined_param(self):
        self.assertRaises(ParamExpandError,
                          self.graph_expander.expand,
                          'foo<m,j> => bar<i,j>')

    def test_graph_fail_param_value_too_high(self):
        self.assertRaises(ParamExpandError,
                          self.graph_expander.expand,
                          'foo<i=4,j><i,j>')


if __name__ == "__main__":
    unittest.main()

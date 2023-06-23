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

from contextlib import suppress
import re
from typing import List, Tuple

from cylc.flow.exceptions import ParamExpandError
from cylc.flow.task_id import TaskID
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults

# To split runtime heading name lists.
REC_NAMES = re.compile(r'(?:[^,<]|<[^>]*>)+')
# To extract (e.g.) 'name', 'the, quick, brown', and 'other' from
#   'name<the, quick, brown>other' (other is used for clock-offsets).
REC_P_ALL = re.compile(r"(%s)?(?:<(.*?)>)?(.+)?" % TaskID.NAME_RE)
# To extract all parameter lists e.g. 'm,n,o' (from '<m,n,o>').
REC_P_GROUP = re.compile(r"<(.*?)>")
# To extract parameter name and optional offset or value e.g. 'm-1'.
REC_P_OFFS = re.compile(
    r'(\w+)\s*([\-+]\s*\d+|=\s*%s)?' % TaskID.NAME_SUFFIX_RE)


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


class NameExpander:
    """Handle parameter expansion in runtime namespace headings."""

    def __init__(self, parameters):
        """Initialize the parameterized task name expander.

        parameters is:
            ({param_name: [param_values],  # list of strings
             {param_name: param_template}) # e.g. "_m%(m)s"
        """
        self.param_cfg, self.param_tmpl_cfg = parameters

    def expand(self, runtime_heading):
        """Expand runtime namespace names for a subset of workflow parameters.

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
                            "parameter %s is not defined in %s" % (
                                pname, runtime_heading))
                    if sval:
                        if sval.startswith('+') or sval.startswith('-'):
                            raise ParamExpandError(
                                "parameter index offsets are not"
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
                                    "parameter %s out of range: %s" % (
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
                raise ParamExpandError('parameter %s is not '
                                       'defined.' % str(exc.args[0]))
        else:
            for param_val in params[0][1]:
                spec_vals[params[0][0]] = param_val
                self._expand_name(results, tmpl, params[1:], spec_vals)

    @staticmethod
    def _parse_task_name_string(task_str: str) -> Tuple[List[str], str]:
        """Takes a parent string and returns a list of parameters and a
        template string.

        Examples:
            >>> this = NameExpander._parse_task_name_string

            # Parent doesn't contain a parameter:
            >>> this('foo')
            ([], 'foo')

            # Parent contains a simple single parameter:
            >>> this('<foo>')
            (['foo'], '{foo}')

            # Parent contains 2 parameters in 1 <>:
            >>> this('something<foo, bar>other')
            (['foo', 'bar'], 'something{foo}{bar}other')

            # Parent contains 2 parameters in 2 <>:
            >>> this('something<foo>middlebit<bar>other')
            (['foo', 'bar'], 'something{foo}middlebit{bar}other')

            # Parent contains 2 parameters, once with an = sign in it.
            >>> this('something<foo=42>middlebit<bar>other')
            (['foo=42', 'bar'], 'something{foo}middlebit{bar}other')

            # Parent contains 2 parameters in 2 <>:
            >>> this('something<foo,bar=99>other')
            (['foo', 'bar=99'], 'something{foo}{bar}other')

            # Parent contains spaces around = sign:
            >>> this('FAM<i = cat ,j=3>')
            (['i = cat', 'j=3'], 'FAM{i}{j}')
        """
        param_list = []

        def _parse_replacement(match: re.Match) -> str:
            nonlocal param_list
            param = match.group(1)
            if ',' in param:
                # parameter syntax `<foo, bar>`
                replacement = ''
                for sub_param in param.split(','):
                    sub_param = sub_param.strip()
                    param_list.append(sub_param)
                    if '=' in sub_param:
                        sub_param = sub_param.split('=')[0].strip()
                    replacement += '{' + sub_param + '}'
            else:
                # parameter syntax: `<foo><bar>`
                param_list.append(param)
                if '=' in param:
                    replacement = '{' + param.split('=')[0] + '}'
                else:
                    replacement = '{' + param + '}'
            return replacement

        replacement = REC_P_GROUP.sub(_parse_replacement, task_str)

        return param_list, replacement

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
        p_list, tmpl = self._parse_task_name_string(parent)

        if not p_list:
            return (None, parent)

        used = {}
        for item in p_list:
            if '-' in item or '+' in item:
                raise ParamExpandError(
                    "parameter offsets illegal here: '%s'" % origin)
            elif '=' in item:
                # Specific value given.
                pname, pval = [val.strip() for val in item.split('=', 1)]
                with suppress(ValueError):
                    pval = int(pval)
                if pname not in self.param_cfg:
                    raise ParamExpandError(
                        "parameter '%s' undefined in '%s'" % (
                            pname, origin))
                elif pval not in self.param_cfg[pname]:
                    raise ParamExpandError(
                        "illegal value '%s=%s' in '%s'" % (
                            pname, pval, origin))
                used[pname] = pval
            else:
                # Non-specific; value must be supplied in param_values.
                try:
                    used[item] = param_values[item]
                except KeyError:
                    raise ParamExpandError(
                        "parameter '%s' undefined in '%s'" % (
                            item, origin))

        # For each parameter substitute the param_tmpl_cfg.
        tmpl = tmpl.format(**self.param_tmpl_cfg)
        # Insert parameter values into template.
        return (used, tmpl % used)


class GraphExpander:
    """Handle parameter expansion of graph string lines."""

    _REMOVE = -32768

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
        """Expand a graph line for subset of workflow parameters.

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
                        "parameter %s is not defined in <%s>: %s" % (
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
                            "parameter %s out of range: %s" % (
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
                    raise ParamExpandError('parameter %s is not '
                                           'defined.' % str(exc.args[0]))
                line = line.replace('<' + p_group + '>', repl)
            if line:
                line_set.add(line)
        else:
            # Recurse through index ranges.
            for param_val in param_list[0][1]:
                values[param_list[0][0]] = param_val
                self._expand_graph(line, all_params,
                                   param_list[1:], line_set, values)

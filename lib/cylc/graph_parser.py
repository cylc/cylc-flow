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
"""Module for parsing cylc graph strings."""

import re
import unittest
from cylc.param_expand import GraphExpander, ParamExpandError
from cylc.task_id import TaskID


ARROW = '=>'


class GraphParseError(Exception):
    """For graph string parsing errors."""
    def __str__(self):
        # Restore some spaces for readability.
        return self.args[0].replace(ARROW, ' %s ' % ARROW)


class Replacement(object):
    """A class to remember match group information in re.sub() calls"""
    def __init__(self, replacement):
        self.replacement = replacement
        self.substitutions = []
        self.match_groups = []

    def __call__(self, match):
        matched = match.group(0)
        replaced = match.expand(self.replacement)
        self.substitutions.append((matched, replaced))
        self.match_groups.append(match.groups())
        return replaced


class GraphParser(object):
    """Class for extracting dependency information from cylc graph strings.

    For each task in the graph string, results are stored as:
        self.triggers[task_name][expression] = ([expr_task_names], suicide)
        self.original[task_name][expression] = original_expression

    (original_expression is separated out to allow comparison of triggers
    from different equivalent expressions, e.g. family vs member).

    This is currently intended to process a single multi-line graph string
    (i.e. the content of a single graph section). But it could be extended to
    store dependencies for the whole suite (call parse_graph multiple times
    and key results by graph section).

    The general form of a dependency is "EXPRESSION => NODE", where:
        * On the right, NODE is a task or family name
        * On the left, an EXPRESSION of nodes involving parentheses, and
          logical operators '&' (AND), and '|' (OR).
        * Node names may be parameterized (any number of parameters):
            NODE<i,j,k>
            NODE<i=0,j,k>  # specific parameter value
            NODE<i-1,j,k>  # offset parameter value
        * A parameterized qualified node name looks like this:
            NODE(<PARAMS>)([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE)
        * The default trigger type is ':succeed'.
        * Trigger qualifiers are ignored on the right to allow chaining:
               "foo => bar => baz & qux"
          Think of this as describing the graph structure first, then
          annotating each node with a trigger type that is only meaningful on
          the left side of each pair (in the default ':succeed' case the
          trigger type can be ommitted, but it is still there in principle).
    """

    OP_AND = '&'
    OP_OR = '|'
    OP_AND_ERR = '&&'
    OP_OR_ERR = '||'
    SUICIDE_MARK = '!'
    TRIG_SUCCEED = ':succeed'
    TRIG_FAIL = ':fail'
    TRIG_FINISH = ':finish'
    FAM_TRIG_EXT_ALL = '-all'
    FAM_TRIG_EXT_ANY = '-any'
    LEN_FAM_TRIG_EXT_ALL = len(FAM_TRIG_EXT_ALL)
    LEN_FAM_TRIG_EXT_ANY = len(FAM_TRIG_EXT_ANY)

    _RE_NODE = r'(?:!)?' + TaskID.NAME_RE
    _RE_PARAMS = r'<[\w,=\-+]+>'
    _RE_OFFSET = r'\[[\w\-\+\^:]+\]'
    _RE_TRIG = r':[\w\-]+'

    # Match fully qualified parameterized single nodes.
    REC_NODE_FULL = re.compile(
        r'''(
        (?:''' +
        _RE_NODE + r'|' + _RE_PARAMS + r'|' + _RE_NODE + _RE_PARAMS +
        ''')                         # node name
        (?:''' + _RE_OFFSET + r''')? # optional cycle point offset
        (?:''' + _RE_TRIG + r''')?   # optional trigger type
        )''', re.X)           # end of string

    # Extract node info from a left-side expression, after parameter expansion.
    REC_NODES = re.compile(r'''
        (''' + _RE_NODE + r''')      # node name
        (''' + _RE_OFFSET + r''')?   # optional cycle point offset
        (''' + _RE_TRIG + r''')?     # optional trigger type
    ''', re.X)

    REC_TRIG_QUAL = re.compile(r'''
        (?:''' + _RE_NODE + r''')    # node name (ignore)
        (''' + _RE_TRIG + r''')?     # optional trigger type
    ''', re.X)

    REC_COMMENT = re.compile('#.*$')

    # Detect presence of expansion parameters in a graph line.
    REC_PARAMS = re.compile(_RE_PARAMS)

    # Detect and extract suite state polling task info.
    REC_SUITE_STATE = re.compile(
        r'(' + TaskID.NAME_RE + ')(<([\w\.\-/]+)::(' + TaskID.NAME_RE + ')(' +
        _RE_TRIG + ')?>)')

    def __init__(self, family_map=None, parameters=None):
        """Initializing the graph string parser.

        family_map (empty or None if no families) is:
            {family_name: [task member names]}
        parameters (empty or None if no parameters) is just passed on to the
        parameter expander classes (documented there).
        """
        self.family_map = family_map or {}
        self.parameters = parameters
        self.triggers = {}
        self.original = {}
        self.suite_state_polling_tasks = {}

    def parse_graph(self, graph_string):
        """Parse the graph string for a single graph section.

        (Assumes any general line-continuation markers have been processed).
           1. Strip comments, whitespace, and blank lines.
              (all whitespace is removed up front so we don't have to consider
              it in regexes and strip it from matched elements)
           2. Join incomplete lines starting or ending with '=>'.
           3. Replicate and expand any parameterized lines.
           4. Split and process by pairs "left-expression => right-node":
              i. Replace families with members (any or all semantics).
             ii. Record parsed dependency information for each right-side node.
        """
        # Strip comments, whitespace, and blank lines.
        non_blank_lines = []
        for line in graph_string.split('\n'):
            line = self.__class__.REC_COMMENT.sub('', line)
            # Apparently this is the fastest way to strip all whitespace!:
            line = "".join(line.split())
            if not line:
                continue
            non_blank_lines.append(line)

        # Join incomplete lines (beginning or ending with an arrow).
        full_lines = []
        part_lines = []
        for i in range(0, len(non_blank_lines)):
            this_line = non_blank_lines[i]
            if i == 0:
                # First line can't start with an arrow.
                if this_line.startswith(ARROW):
                    raise GraphParseError(
                        "ERROR, leading arrow: %s" % this_line)
            try:
                next_line = non_blank_lines[i + 1]
            except IndexError:
                next_line = ''
                if this_line.endswith(ARROW):
                    # Last line can't end with an arrow.
                    raise GraphParseError(
                        "ERROR, trailing arrow: %s" % this_line)
            part_lines.append(this_line)
            if (this_line.endswith(ARROW) or next_line.startswith(ARROW)):
                continue
            full_line = ''.join(part_lines)

            # Record inter-suite dependence and remove the marker notation.
            # ("foo<SUITE::TASK:fail> => bar" becomes:fail "foo => bar").
            repl = Replacement('\\1')
            full_line = self.__class__.REC_SUITE_STATE.sub(repl, full_line)
            for item in repl.match_groups:
                l_task, r_all, r_suite, r_task, r_status = item
                if r_status:
                    r_status = r_status[1:]
                else:
                    r_status = self.__class__.TRIG_SUCCEED[1:]
                self.suite_state_polling_tasks[l_task] = (
                    r_suite, r_task, r_status, r_all)
            full_lines.append(full_line)
            part_lines = []

        # Check for double-char conditional operators (a common mistake),
        # and bad node syntax (order of qualifiers).
        bad_lines = []
        for line in full_lines:
            if self.__class__.OP_AND_ERR in line:
                raise GraphParseError(
                    "ERROR, the graph AND operator is '%s': %s" % (
                        self.__class__.OP_AND, line))
            if self.__class__.OP_OR_ERR in line:
                raise GraphParseError(
                    "ERROR, the graph OR operator is '%s': %s" % (
                        self.__class__.OP_OR, line))
            # Check node syntax. First drop all non-node characters.
            node_str = line
            for s in ['=>', '|', '&', '(', ')', '!']:
                node_str = node_str.replace(s, ' ')
            # Then drop all valid nodes, longest first to avoid sub-strings.
            nodes = self.__class__.REC_NODE_FULL.findall(node_str)
            nodes.sort(key=len, reverse=True)
            for node in nodes:
                node_str = node_str.replace(node, '')
            # Result should be empty string.
            if node_str.strip():
                bad_lines.append(line.strip())
        if bad_lines:
            raise GraphParseError(
                "ERROR, bad graph node format:\n"
                "  " + "\n  ".join(bad_lines) + "\n"
                "Correct format is"
                " NAME(<PARAMS>)([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE)")

        # Expand parameterized lines (or detect undefined parameters).
        line_set = set()
        graph_expander = GraphExpander(self.parameters)
        for line in full_lines:
            if not self.__class__.REC_PARAMS.search(line):
                line_set.add(line)
                continue
            try:
                for l in graph_expander.expand(line):
                    line_set.add(l)
            except ParamExpandError as exc:
                raise GraphParseError(str(exc))

        # Process chains of dependencies as pairs: left => right.
        # Parameterization can duplicate some dependencies, so use a set.
        pairs = set()
        for line in line_set:
            # "foo => bar => baz" becomes [foo, bar, baz]
            chain = line.split(ARROW)
            # Auto-trigger lone nodes and initial nodes in a chain.
            for name, offset, _ in self.__class__.REC_NODES.findall(chain[0]):
                if not offset:
                    pairs.add((None, name))
            for i in range(0, len(chain) - 1):
                pairs.add((chain[i], chain[i + 1]))

        for pair in pairs:
            self._proc_dep_pair(pair[0], pair[1])

        # If debugging, print the final result here:
        # self.print_triggers()

    def _proc_dep_pair(self, left, right):
        """Process a single dependency pair 'left => right'.

        'left' can be a logical expression of qualified node names.
        'right' can be one or more node names joined by AND.
        A node name is a task name or a family name.
        A qualified name is NAME([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE).
        Trigger qualifiers, but not cycle offsets, are ignored on the right to
        allow chaining.
        """
        # Raise error for right-hand-side OR operators.
        if right and self.__class__.OP_OR in right:
            raise GraphParseError("ERROR, illegal OR on RHS: %s" % right)

        # Remove qualifiers from right-side nodes.
        if right:
            for qual in self.__class__.REC_TRIG_QUAL.findall(right):
                right = right.replace(qual, '')

        # Raise error if suicide triggers on the left of the trigger.
        if left and self.__class__.SUICIDE_MARK in left:
            raise GraphParseError(
                "ERROR, suicide markers must be"
                " on the right of a trigger: %s" % left)

        # Cycle point offsets are not allowed on the right side (yet).
        if right and '[' in right:
            raise GraphParseError(
                "ERROR, illegal cycle point offset on the right: %s => %s" % (
                    left, right))

        # Check that parentheses match.
        if left and left.count("(") != left.count(")"):
            raise GraphParseError(
                "ERROR, parenthesis mismatch in: \"" + left + "\"")

        # Split right side on AND.
        rights = right.split(self.__class__.OP_AND)
        if '' in rights or right and not all(rights):
            raise GraphParseError(
                "ERROR, null task name in graph: %s=>%s" % (left, right))

        if not left or (self.__class__.OP_OR in left or '(' in left):
            # Treat conditional or bracketed expressions as a single entity.
            lefts = [left]
        else:
            # Split non-conditional left-side expressions on AND.
            lefts = left.split(self.__class__.OP_AND)
        if '' in lefts or left and not all(lefts):
            raise GraphParseError(
                "ERROR, null task name in graph: %s=>%s" % (left, right))

        for left in lefts:
            # Extract information about all nodes on the left.

            if left:
                info = self.__class__.REC_NODES.findall(left)
                expr = left
            else:
                # There is no left-hand-side task.
                info = []
                expr = ''

            # Make success triggers explicit.
            n_info = []
            for name, offset, trig in info:
                if not trig:
                    trig = self.__class__.TRIG_SUCCEED
                    if offset:
                        this = r'\b%s\b%s(?!:)' % (
                            re.escape(name), re.escape(offset))
                    else:
                        this = r'\b%s\b(?![\[:])' % re.escape(name)

                    that = name + offset + trig
                    expr = re.sub(this, that, expr)
                n_info.append((name, offset, trig))
            info = n_info

            # Determine semantics of all family triggers present.
            family_trig_map = {}
            for name, offset, trig in info:
                if name in self.family_map:
                    if trig.endswith(self.__class__.FAM_TRIG_EXT_ANY):
                        ttype = trig[:-self.__class__.LEN_FAM_TRIG_EXT_ANY]
                        ext = self.__class__.FAM_TRIG_EXT_ANY
                    elif trig.endswith(self.__class__.FAM_TRIG_EXT_ALL):
                        ttype = trig[:-self.__class__.LEN_FAM_TRIG_EXT_ALL]
                        ext = self.__class__.FAM_TRIG_EXT_ALL
                    else:
                        # Unqualified (FAM => foo) or bad (FAM:bad => foo).
                        raise GraphParseError(
                            "ERROR, bad family trigger in %s" % expr)
                    family_trig_map[(name, trig)] = (ttype, ext)
                else:
                    if (trig.endswith(self.__class__.FAM_TRIG_EXT_ANY) or
                            trig.endswith(self.__class__.FAM_TRIG_EXT_ALL)):
                        raise GraphParseError("ERROR, family trigger on non-"
                                              "family namespace %s" % expr)
            self._families_all_to_all(expr, rights, info, family_trig_map)

    def _families_all_to_all(self, expr, rights, info, family_trig_map):
        """Replace all family names with member names, for all/any semantics.

        (Also for graph segments with no family names.)
        """
        n_info = []
        n_expr = expr
        for name, offset, trig in info:
            if (name, trig) in family_trig_map:
                ttype, extn = family_trig_map[(name, trig)]
                m_info = []
                m_expr = []
                for mem in self.family_map[name]:
                    m_info.append((mem, offset, ttype))
                    m_expr.append("%s%s%s" % (mem, offset, ttype))
                this = r'\b%s%s%s\b' % (name, re.escape(offset), trig)
                if extn == self.__class__.FAM_TRIG_EXT_ALL:
                    that = '(%s)' % '&'.join(m_expr)
                elif extn == self.__class__.FAM_TRIG_EXT_ANY:
                    that = '(%s)' % '|'.join(m_expr)
                n_expr = re.sub(this, that, n_expr)
                n_info += m_info
            else:
                n_info += [(name, offset, trig)]
        self._add_trigger(expr, rights, n_expr, n_info)

    def _add_trigger(self, orig_expr, rights, expr, info):
        """Store trigger info from "expr => right".

        Arg info is [(name, offset, trigger_type)] for each name in expr.
        """
        trigs = []
        for name, offset, trigger in info:
            # Replace finish triggers (must be done after member substn).
            if trigger == self.__class__.TRIG_FINISH:
                this = "%s%s%s" % (name, offset, trigger)
                that = "(%s%s%s%s%s%s%s)" % (
                    name, offset, self.__class__.TRIG_SUCCEED,
                    self.__class__.OP_OR,
                    name, offset, self.__class__.TRIG_FAIL)
                expr = expr.replace(this, that)
                trigs += [
                    "%s%s%s" % (name, offset, self.__class__.TRIG_SUCCEED),
                    "%s%s%s" % (name, offset, self.__class__.TRIG_FAIL)]
            else:
                trigs += ["%s%s%s" % (name, offset, trigger)]

        for right in rights:
            suicide = right.startswith(self.__class__.SUICIDE_MARK)
            if suicide:
                right = right[1:]
            if right in self.family_map:
                members = self.family_map[right]
            else:
                members = [right]
            for member in members:
                self.triggers.setdefault(member, {})
                self.original.setdefault(member, {})
                self.triggers[member][expr] = (trigs, suicide)
                self.original[member][expr] = orig_expr

    def print_triggers(self):
        for right, val in self.triggers.items():
            for expr, info in val.items():
                triggers, suicide = info
                if suicide:
                    title = "SUICIDE:"
                else:
                    title = "TRIGGER:"
                print '\nTASK:', right
                print ' ', title, expr
                for t in triggers:
                    print '    +', t
                print '  from', self.original[right][expr]


class TestGraphParser(unittest.TestCase):
    """Unit tests for the GraphParser class."""

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
        gp = GraphParser()
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo[-P1Y]<m,n> => bar")
        self.assertRaises(
            GraphParseError, gp.parse_graph, "foo[-P1Y]<m,n> => bar")
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


if __name__ == "__main__":
    unittest.main()

#!usr/bin/env python

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
import sys
import unittest
from copy import copy
from cylc.param_expand import GraphExpander

"""Module for parsing cylc graph strings."""


class GraphParseError(Exception):
    """For graph string parsing errors."""
    pass


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
        * Default trigger type is ':succeed'.
        * Chaining is allowed ("foo => bar => baz") but only unqualified nodes
          can appear on the right of an arrow because expressions and
          trigger-types make no sense there.
          TODO: however we COULD choose to ignore qualifiers on the right? E.g.
             "foo => bar:fail => baz"
          would be equivalent to:
             "foo:succeed => bar", and "bar:fail => baz"

    """

    ARROW = '=>'
    OP_AND = '&'
    OP_OR = '|'
    OP_AND_ERR = '&&'
    OP_OR_ERR = '||'
    SUICIDE_MARK = '!'
    TRIG_SEP = ':'
    TRIG_SUCCEED = ':succeed'
    TRIG_FAIL = ':fail'
    TRIG_FINISH = ':finish'
    FAM_TRIG_EXT_ALL = '-all'
    FAM_TRIG_EXT_ANY = '-any'
    FAM_TRIG_EXT_MEM = '-mem'
    LEN_FAM_TRIG_EXT_ALL = len(FAM_TRIG_EXT_ALL)
    LEN_FAM_TRIG_EXT_ANY = len(FAM_TRIG_EXT_ANY)
    LEN_FAM_TRIG_EXT_MEM = len(FAM_TRIG_EXT_MEM)

    # Match full parameterized single nodes.
    REC_NODE_FULL_SINGLE = re.compile(r'''
    ^                     # beginning of string
    ((?:!)?\w[\w\-+%@]*)  # node name
    (<[\w,=\-+ ]+>)?      # optional parameter list
    (\[[\w\-\+\^]+\])?    # optional cycle point offset
    (:[\w\-]+)?           # optional trigger type
    $
    ''', re.X)           # end of string

    # To extract node info from a left-side dependency group.
    REC_NODES = re.compile(r'''
    ((?:!)?\w[\w\-+%@]*)  # node name
    (\[[\w\-\+\^]+\])?    # optional cycle point offset
    (:[\w\-]+)?           # optional trigger type
    ''', re.X)

    REC_COMMENT = re.compile('#.*$')

    # Detect presence of expansion parameters in a graph line.
    REC_PARAMETERS = re.compile(r'<[\w,=\-+ ]+>')

    # Detect and extract suite state polling task info.
    REC_SUITE_STATE = re.compile('(\w+)(<([\w\.\-]+)::(\w+)(:\w+)?>)')

    def __init__(self, family_map=None, parameters=None):
        """Store suite data that affects graph parsing."""
        self.family_map = family_map or {}
        self.parameters = parameters or {}
        self.triggers = {}
        self.original = {}
        self.suite_state_polling_tasks = {}

    def parse_graph(self, graph_string):
        """Parse the graph string for a single graph section.

        (Assumes any general line-continuation markers have been processed).
           1. Strip comments and blank lines.
           2. Join incomplete lines starting or ending with '=>'.
           3. Replicate and expand any parameterized lines.
           4. Split and process by pairs "left-expression => right-node":
              i. Replace families with members (member, all, or any semantics).
             ii. Record parsed dependency information for each right-side node.
        """
        # Strip comments and skip blank lines.
        non_blank_lines = []
        for line in graph_string.split('\n'):
            line = self.__class__.REC_COMMENT.sub('', line)
            line = line.strip()
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
                if this_line.startswith(self.__class__.ARROW):
                    raise GraphParseError(
                        "ERROR, leading arrow: %s" % this_line)
            try:
                next_line = non_blank_lines[i + 1]
            except IndexError:
                next_line = ''
                if this_line.endswith(self.__class__.ARROW):
                    # Last line can't end with an arrow.
                    raise GraphParseError(
                        "ERROR, trailing arrow: %s" % this_line)
            part_lines.append(this_line)
            if (this_line.endswith(self.__class__.ARROW) or
                    next_line.startswith(self.__class__.ARROW)):
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
        bad_nodes = set()
        for line in full_lines:
            if self.__class__.OP_AND_ERR in line:
                raise GraphParseError(
                    "ERROR, the graph AND operator is '%s': %s" % (
                        self.__class__.OP_AND, line))
            if self.__class__.OP_OR_ERR in line:
                raise GraphParseError(
                    "ERROR, the graph OR operator is '%s': %s" % (
                        self.__class__.OP_OR, line))
            # Check node syntax (first drop all non-node characters).
            node_str = line
            for s in ['=>', '|', '&', '(', ')', '!']:
                node_str = node_str.replace(s, ' ')
            for node in node_str.split():
                if not self.__class__.REC_NODE_FULL_SINGLE.match(node):
                    bad_nodes.add(node)
        if bad_nodes:
            raise GraphParseError(
                "Syntax error; graph nodes must match: \n"
                "     NAME(<PARAMS>)([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE)\n" +
                "  " + "\n  ".join(bad_nodes))

        # Expand parameterized lines.
        line_set = set()
        graph_expander = GraphExpander(self.parameters)
        for line in full_lines:
            if not self.__class__.REC_PARAMETERS.search(line):
                line_set.add(line)
                continue
            for l in graph_expander.expand(line):
                line_set.add(l)

        # Process chains of dependencies as pairs: left => right.
        # Parameterization can duplicate some dependencies, so use a set.
        pairs = set()
        for line in line_set:
            # "foo => bar => baz" becomes [foo, bar, baz]
            chain = line.split(self.__class__.ARROW)
            # Auto-trigger lone nodes and initial nodes in a chain.
            for name, offset, _ in self.__class__.REC_NODES.findall(chain[0]):
                if not offset:
                    pairs.add(('', name))
            for i in range(0, len(chain) - 1):
                pairs.add((chain[i].strip(), chain[i + 1].strip()))

        for pair in pairs:
            self._proc_dep_pair(pair[0], pair[1])

        # If debugging, print the final result here:
        # self.print_triggers()

    def _proc_dep_pair(self, left, right):
        """Process a single dependency pair 'left => right'.

        'left' can be a logical expression of qualified node names.
        'right' can be one or more unqualified node names joined by AND.
        A node name is a task name or a family name.
        A qualified name is NAME([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE).
        """
        if self.__class__.OP_OR in right:
            raise GraphParseError("ERROR, illegal OR on RHS: %s" % right)
        if self.__class__.TRIG_SEP in right:
            raise GraphParseError(
                "ERROR, illegal trigger qualifier on RHS: %s" % right)
        if self.__class__.SUICIDE_MARK in left:
            raise GraphParseError(
                "ERROR, suicide markers must be"
                " on the right of a trigger: %s" % left)
        # Cycle point offsets are not allowed on the right side (yet).
        if '[' in right:
            raise GraphParseError(
                "ERROR, illegal cycle point offset on the right: %s" % right)
        # Check that parentheses match.
        if left.count("(") != left.count(")"):
            raise GraphParseError(
                "ERROR, parenthesis mismatch in: \"" + left + "\"")

        # Split right side on AND.
        rights = [r.strip() for r in right.split(self.__class__.OP_AND)]

        if self.__class__.OP_OR in left or '(' in left:
            # Treat conditional or bracketed expressions as a single entity.
            lefts = [left]
        else:
            # Split non-conditional left-side expressions on AND.
            lefts = [
                l.strip() for l in left.split(self.__class__.OP_AND)]

        for left in lefts:
            # Extract infomation about all nodes on the left.
            info = self.__class__.REC_NODES.findall(left)

            # Make success triggers explicit.
            n_info = []
            expr = left
            for name, offset, trig in info:
                offset = offset or ''
                if not trig:
                    trig = self.__class__.TRIG_SUCCEED
                    this = r'\b%s\b%s' % (name, re.escape(offset))
                    that = name + offset + trig
                    expr = re.sub(this, that, expr)
                n_info.append((name, offset, trig))
            info = n_info

            # Determine semantics of all family triggers present.
            families = {}
            semantics = set()
            for name, offset, trig in info:
                if name in self.family_map:
                    # TODO - USE OF 'semantics' HERE IS A BIT POINTLESS;
                    # ALL-TO-ALL SHOULD DISTINGUISH ALL-TO-ANY HERE INSTEAD OF
                    # DEFERRING TO LATER.
                    if trig.endswith(self.__class__.FAM_TRIG_EXT_ANY):
                        ttype = trig[:-self.__class__.LEN_FAM_TRIG_EXT_ANY]
                        ext = self.__class__.FAM_TRIG_EXT_ANY
                        semantics.add('all-to-all')
                    elif trig.endswith(self.__class__.FAM_TRIG_EXT_ALL):
                        ttype = trig[:-self.__class__.LEN_FAM_TRIG_EXT_ALL]
                        ext = self.__class__.FAM_TRIG_EXT_ALL
                        semantics.add('all-to-all')
                    elif trig.endswith(self.__class__.FAM_TRIG_EXT_MEM):
                        ttype = trig[:-self.__class__.LEN_FAM_TRIG_EXT_MEM]
                        ext = self.__class__.FAM_TRIG_EXT_MEM
                        semantics.add('mem-to-mem')
                    else:
                        raise GraphParseError(
                            "ERROR, unqualified family trigger in %s" % expr)
                    families[name] = (ttype, ext)
                else:
                    if (trig.endswith(self.__class__.FAM_TRIG_EXT_ANY) or
                            trig.endswith(self.__class__.FAM_TRIG_EXT_ALL) or
                            trig.endswith(self.__class__.FAM_TRIG_EXT_MEM)):
                        raise GraphParseError("ERROR, family trigger on non-"
                                              "family namespace %s" % expr)
            if len(set(semantics)) > 1:
                raise GraphParseError(
                    "ERROR, mixed family semantics: %s" % expr)

            if 'mem-to-mem' in semantics:
                # This requires duplication of the graph line segment.
                self._families_mem_to_mem(expr, rights, info, families)
            else:
                # Non-family or all/any family semantics.
                self._families_all_to_all(expr, rights, info, families)

    def _families_mem_to_mem(self, expr, rights, info, families):
        """Expand for member-to-member family semantics.

        Valid for same-size same-sort families.
        E.g. "FAM => BAM" means "fam_a => bam_a", "fam_b => bam_b", etc.
        """
        sizes = set()
        for fam in families:
            sizes.add(len(self.family_map[fam]))
        if len(sizes) > 1:
            raise GraphParseError(
                "ERROR, member-to-member family triggers require"
                " family sizes to be the same: %s" % expr)

        for i in range(0, sizes.pop()):
            i_info = []
            i_expr = expr
            for name, offset, trig in info:
                ttype, _ = families[name]
                if name in families:
                    mem = sorted(self.family_map[name])[i]
                    this = r'\b%s%s%s\b' % (name, re.escape(offset), trig)
                    that = '%s%s%s' % (mem, offset, ttype)
                    i_expr = re.sub(this, that, i_expr)
                    i_info.append((mem, offset, ttype))
                else:
                    i_info.append((name, offset, ttype))

            for right in rights:
                if right.startswith(self.__class__.SUICIDE_MARK):
                    right = right[1:].strip()
                    suicide = True
                else:
                    suicide = False
                if right in self.family_map:
                    mem = sorted(self.family_map[right])[i]
                    self._add_trigger(expr, mem, i_expr, i_info, suicide)
                else:
                    self._add_trigger(expr, right, i_expr, i_info, suicide)

    def _families_all_to_all(self, expr, rights, info, families):
        """Replace all family names with member names, for all/any semantics.

        (Also for graph segments with no family names.)
        """
        n_info = []
        n_expr = expr
        for name, offset, trig in info:
            if name in families:
                ttype, extn = families[name]
                m_info = []
                m_expr = []
                for mem in self.family_map[name]:
                    m_info.append((mem, offset, ttype))
                    m_expr.append("%s%s%s" % (mem, offset, ttype))
                this = r'\b%s%s%s\b' % (name, re.escape(offset), trig)
                if extn == self.__class__.FAM_TRIG_EXT_ALL:
                    that = '(%s)' % ' & '.join(m_expr)
                elif extn == self.__class__.FAM_TRIG_EXT_ANY:
                    that = '(%s)' % ' | '.join(m_expr)
                n_expr = re.sub(this, that, n_expr)
                n_info += m_info
            else:
                n_info += [(name, offset, trig)]
        info = n_info

        for right in rights:
            if right.startswith(self.__class__.SUICIDE_MARK):
                right = right[1:].strip()
                suicide = True
            else:
                suicide = False
            if right in self.family_map:
                for mem in self.family_map[right]:
                    self._add_trigger(expr, mem, n_expr, info, suicide)
            else:
                self._add_trigger(expr, right, n_expr, info, suicide)

    def _add_trigger(self, orig_expr, right, expr, info, suicide):
        """Store trigger info from "expr => right" for a single task ('right').

        Arg info is [(name, offset, trigger_type)] for each name in expr.
        """
        # Replace finish triggers here (must be done after member substn).
        trigs = []
        for name, offset, trigger in info:
            if trigger == self.__class__.TRIG_FINISH:
                this = "%s%s%s" % (name, re.escape(offset), trigger)
                that = "(%s%s%s %s %s%s%s)" % (
                    name, offset, self.__class__.TRIG_SUCCEED,
                    self.__class__.OP_OR,
                    name, offset, self.__class__.TRIG_FAIL)
                expr = re.sub(this, that, expr)
                trigs += [
                    "%s%s%s" % (name, offset, self.__class__.TRIG_SUCCEED),
                    "%s%s%s" % (name, offset, self.__class__.TRIG_FAIL)]
            else:
                trigs += ["%s%s%s" % (name, offset, trigger)]

        if right not in self.triggers:
            self.triggers[right] = {}
            self.original[right] = {}
        self.triggers[right][expr] = (trigs, suicide)
        self.original[right][expr] = orig_expr

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
    """Unit tests for the GraphParser class.

    Method doc strings are ommitted; the tests should self-explanatory.
    """

    def test_line_continuation(self):
        """Text syntax-driven line continuation."""

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
        """Test default trigger is :succeed.
        """
        gp1 = GraphParser()
        gp1.parse_graph("foo => bar")
        gp2 = GraphParser()
        gp2.parse_graph("foo:succeed => bar")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_finish_trigger(self):
        """Test finish trigger expansion.
        """
        gp1 = GraphParser()
        gp1.parse_graph("foo:finish => bar")
        gp2 = GraphParser()
        gp2.parse_graph("(foo:succeed | foo:fail) => bar")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_mem_to_mem(self):
        """Test family member-to-member semantics.
        """
        fam_map = {
            'FAM': ['f1', 'f2'],
            'BAM': ['b1', 'b2'],
            'WAM': ['w1', 'w2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:succeed-mem | BAM:succeed-mem => WAM")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("""
            f1 | b1 => w1
            f2 | b2 => w2""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_all_to_all(self):
        """Test family all-to-all semantics.
        """
        fam_map = {'FAM': ['m1', 'm2'], 'BAM': ['b1', 'b2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:succeed-all => BAM")

        gp2 = GraphParser(fam_map)
        gp2.parse_graph("""
            (m1 & m2) => b1
            (m1 & m2) => b2""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_one_to_all(self):
        """Test family one-to-all semantics.
        """
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
        """Test family all-to-one semantics.
        """
        fam_map = {'FAM': ['m1', 'm2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:succeed-all => post")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("(m1 & m2) => post")
        self.assertEqual(gp1.triggers, gp2.triggers)

        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:succeed-mem => post")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("""
            m1 => post
            m2 => post
            """)
        self.assertEqual(gp1.triggers, gp2.triggers)
        gp3 = GraphParser(fam_map)
        gp3.parse_graph("""
            m1 & m2 => post
            """)
        self.assertEqual(gp1.triggers, gp3.triggers)

    def test_fam_any_to_one(self):
        """Test family any-to-one semantics.
        """
        fam_map = {'FAM': ['m1', 'm2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:succeed-any => post")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("(m1 | m2) => post")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_any_to_all(self):
        """Test family any-to-all semantics.
        """
        fam_map = {'FAM': ['m1', 'm2'], 'BAM': ['b1', 'b2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:fail-any => BAM")

        gp2 = GraphParser(fam_map)
        gp2.parse_graph("""
            (m1:fail | m2:fail) => b1
            (m1:fail | m2:fail) => b2""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_finish(self):
        """Test family finish semantics.
        """
        fam_map = {'FAM': ['m1', 'm2']}
        gp1 = GraphParser(fam_map)
        gp1.parse_graph("FAM:finish-all => post")
        gp2 = GraphParser(fam_map)
        gp2.parse_graph("""
            ((m1:succeed | m1:fail) & (m2:succeed | m2:fail)) => post""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_parameter_expand(self):
        # See also the unit tests in lib/cylc/param_expand.py.
        fam_map = {
            'FAM_m0': ['fa_m0', 'fb_m0'],
            'FAM_m1': ['fa_m1', 'fb_m1'],
        }
        params = {
            'm': ['0', '1'], 'n': ['0', '1'],
            'templates': {
                'm': '_m%(m)s',
                'n': '_n%(n)s',
            }
        }
        gp1 = GraphParser(fam_map, params)
        gp1.parse_graph("""
            pre => foo<m,n> => bar<n>
            bar<n=0> => baz  # specific case
            bar<n-1> => bar<n>  # inter-chunk
            FAM<m>:succeed-mem => post
            """)
        gp2 = GraphParser()
        gp2.parse_graph("""
            pre => foo_m0_n0 => bar_n0
            pre => foo_m0_n1 => bar_n1
            pre => foo_m1_n0 => bar_n0
            pre => foo_m1_n1 => bar_n1
            bar_n0 => baz
            bar_n0 => bar_n1
            fa_m0 & fa_m1 & fb_m0 & fb_m1 => post
            """)
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_conditional(self):
        gp1 = GraphParser()
        gp1.parse_graph("(foo:start | bar) => baz")
        res = {
            'baz': {
                '(foo:start | bar:succeed)': (
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
        # Repeating a trigger should have no effect.
        gp1 = GraphParser()
        gp2 = GraphParser()
        gp1.parse_graph("foo => bar")
        gp2.parse_graph("""
            foo => bar
            foo => bar""")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_suicide_trigger(self):
        # Test whitespace before a suicide trigger.
        gp1 = GraphParser()
        gp2 = GraphParser()
        gp1.parse_graph("foo => !bar")
        gp2.parse_graph("foo => ! bar")
        self.assertEqual(gp1.triggers, gp2.triggers)

    def test_fam_qualifiers_rhs(self):
        graph = "foo => FAM:succeed-all => bar"
        gp = GraphParser()
        self.assertRaises(GraphParseError, gp.parse_graph, graph)

    def test_double_oper(self):
        graph = "foo && bar => baz"
        gp = GraphParser()
        self.assertRaises(GraphParseError, gp.parse_graph, graph)
        graph = "foo || bar => baz"
        gp = GraphParser()
        self.assertRaises(GraphParseError, gp.parse_graph, graph)

    def test_bad_node_syntax(self):
        # Should be:
        #   NAME(<PARAMS>)([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE)")
        graphs = [
            "foo[-P1Y]<m,n> => bar",
            "foo[-P1Y]<m,n> => bar",
            "foo:fail[-P1Y] => bar",
            "foo[-P1Y]:fail<m,n> => bar",
            "foo[-P1Y]<m,n>:fail => bar",
            "foo<m,n>:fail[-P1Y] => bar",
            "foo:fail<m,n>[-P1Y] => bar"
        ]
        for graph in graphs:
            gp = GraphParser()
            self.assertRaises(GraphParseError, gp.parse_graph, graph)

if __name__ == "__main__":
    unittest.main()

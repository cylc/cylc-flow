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
"""Module for parsing cylc graph strings."""

import re

from cylc.exceptions import GraphParseError
from cylc.param_expand import GraphExpander
from cylc.task_id import TaskID


ARROW = '=>'


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
        * A remote suite qualified node name looks like this:
            NODE(<REMOTE-SUITE-TRIGGER>)(:TRIGGER-TYPE)
        * Trigger qualifiers are ignored on the right to allow chaining:
               "foo => bar => baz & qux"
          Think of this as describing the graph structure first, then
          annotating each node with a trigger type that is only meaningful on
          the left side of each pair (in the default ':succeed' case the
          trigger type can be omitted, but it is still there in principle).
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

    _RE_SUICIDE = r'(?:!)?'
    _RE_NODE = _RE_SUICIDE + TaskID.NAME_RE
    _RE_NODE_OR_ACTION = r'(?:[!@])?' + TaskID.NAME_RE

    _RE_PARAMS = r'<[\w,=\-+]+>'
    _RE_OFFSET = r'\[[\w\-\+\^:]+\]'
    _RE_TRIG = r':[\w\-]+'

    # Match if there are any spaces which could lead to graph problems
    REC_GRAPH_BAD_SPACES_LINE = re.compile(
        TaskID.NAME_RE +
        r'''
        (?<![\-+](?=\s*[0-9])) # allow spaces after -+ if numbers follow
        (?!\s*[\-+]\s*[0-9])   # allow spaces before/after -+ if numbers follow
        \s+                    # do not allow 'task<space>task'
        ''' + TaskID.NAME_SUFFIX_RE, re.X)

    # Match @actions.
    REC_ACTION = re.compile(r'@[\w\-+%]+')

    # Match fully qualified parameterized single nodes.
    REC_NODE_FULL = re.compile(
        _RE_SUICIDE +
        r'''
        (?:(?:''' +
        TaskID.NAME_RE + r'(?:' + _RE_PARAMS + r')?|' + _RE_PARAMS +
        ''')                             # node name
        )+                               # allow task<param> to repeat
        (?:''' + _RE_OFFSET + r''')?     # optional cycle point offset
        (?:''' + _RE_TRIG + r''')?       # optional trigger type
        ''', re.X)                       # end of string

    # Extract node or action from left-side expressions after param expansion.
    REC_NODES = re.compile(r'''
        (''' + _RE_NODE_OR_ACTION + r''')      # node name
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
        r'(' + TaskID.NAME_RE + r')(<([\w.\-/]+)::(' +
        TaskID.NAME_RE + r')(' + _RE_TRIG + r')?>)')

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
        bad_lines = []
        for line in graph_string.split('\n'):
            modified_line = self.__class__.REC_COMMENT.sub('', line)

            # Ignore empty lines
            if not modified_line or modified_line.isspace():
                continue

            # Catch simple bad lines that would be accepted once
            # spaces are removed, e.g. 'foo bar => baz'
            if self.REC_GRAPH_BAD_SPACES_LINE.search(modified_line):
                bad_lines.append(line)
                continue

            # Apparently this is the fastest way to strip all whitespace!:
            modified_line = "".join(modified_line.split())
            non_blank_lines.append(modified_line)

        # Check if there were problem lines and abort
        if bad_lines:
            self._report_invalid_lines(bad_lines)

        # Join incomplete lines (beginning or ending with an arrow).
        full_lines = []
        part_lines = []
        for i, _ in enumerate(non_blank_lines):
            this_line = non_blank_lines[i]
            if i == 0:
                # First line can't start with an arrow.
                if this_line.startswith(ARROW):
                    raise GraphParseError(
                        "leading arrow: %s" % this_line)
            try:
                next_line = non_blank_lines[i + 1]
            except IndexError:
                next_line = ''
                if this_line.endswith(ARROW):
                    # Last line can't end with an arrow.
                    raise GraphParseError(
                        "trailing arrow: %s" % this_line)
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
                    "the graph AND operator is '%s': %s" % (
                        self.__class__.OP_AND, line))
            if self.__class__.OP_OR_ERR in line:
                raise GraphParseError(
                    "the graph OR operator is '%s': %s" % (
                        self.__class__.OP_OR, line))
            # Check node syntax. First drop all non-node characters.
            node_str = line
            for s in ['=>', '|', '&', '(', ')', '!']:
                node_str = node_str.replace(s, ' ')
            # Drop all valid @triggers, longest first to avoid sub-strings.
            nodes = self.__class__.REC_ACTION.findall(node_str)
            nodes.sort(key=len, reverse=True)
            for node in nodes:
                node_str = node_str.replace(node, '')
            # Then drop all valid nodes, longest first to avoid sub-strings.
            bad_lines = [node_str for node in node_str.split()
                         if self.__class__.REC_NODE_FULL.sub('', node, 1)]
        if bad_lines:
            self._report_invalid_lines(bad_lines)

        # Expand parameterized lines (or detect undefined parameters).
        line_set = set()
        graph_expander = GraphExpander(self.parameters)
        for line in full_lines:
            if not self.__class__.REC_PARAMS.search(line):
                line_set.add(line)
                continue
            for l in graph_expander.expand(line):
                line_set.add(l)

        # Process chains of dependencies as pairs: left => right.
        # Parameterization can duplicate some dependencies, so use a set.
        pairs = set()
        for line in line_set:
            # "foo => bar => baz" becomes [foo, bar, baz]
            chain = line.split(ARROW)
            # Auto-trigger lone nodes and initial nodes in a chain.
            for name, offset, _ in self.__class__.REC_NODES.findall(chain[0]):
                if not offset and not name.startswith('@'):
                    pairs.add((None, name))
            for i in range(0, len(chain) - 1):
                pairs.add((chain[i], chain[i + 1]))

        for pair in pairs:
            self._proc_dep_pair(pair[0], pair[1])

    @classmethod
    def _report_invalid_lines(cls, lines):
        """Raise GraphParseError in a consistent format when there are
        lines with bad syntax.

        The list of bad lines are inserted into the error message to show
        exactly what lines have problems. The correct syntax of graph lines
        is displayed to direct people on the correct path.

        Keyword Arguments:
        lines -- a list of bad graph lines to be reported

        Raises:
        GraphParseError -- always. This is the sole purpose of this method
        """
        raise GraphParseError(
            "bad graph node format:\n"
            "  " + "\n  ".join(lines) + "\n"
            "Correct format is:\n"
            " @ACTION or "
            " NAME(<PARAMS>)([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE)\n"
            " {NAME(<PARAMS>) can also be: "
            "<PARAMS>NAME or NAME<PARAMS>NAME_CONTINUED}\n"
            " or\n"
            " NAME(<REMOTE-SUITE-TRIGGER>)(:TRIGGER-TYPE)")

    def _proc_dep_pair(self, left, right):
        """Process a single dependency pair 'left => right'.

        'left' can be a logical expression of qualified node names.
        'right' can be one or more node names joined by AND.
        A node is an xtrigger, or a task or a family name.
        A qualified name is NAME([CYCLE-POINT-OFFSET])(:TRIGGER-TYPE).
        Trigger qualifiers, but not cycle offsets, are ignored on the right to
        allow chaining.
        """
        # Raise error for right-hand-side OR operators.
        if right and self.__class__.OP_OR in right:
            raise GraphParseError("illegal OR on RHS: %s" % right)

        # Remove qualifiers from right-side nodes.
        if right:
            for qual in self.__class__.REC_TRIG_QUAL.findall(right):
                right = right.replace(qual, '')

        # Raise error if suicide triggers on the left of the trigger.
        if left and self.__class__.SUICIDE_MARK in left:
            raise GraphParseError(
                "suicide markers must be"
                " on the right of a trigger: %s" % left)

        # Cycle point offsets are not allowed on the right side (yet).
        if right and '[' in right:
            raise GraphParseError(
                "illegal cycle point offset on the right: %s => %s" % (
                    left, right))

        # Check that parentheses match.
        if left and left.count("(") != left.count(")"):
            raise GraphParseError(
                "parenthesis mismatch in: \"" + left + "\"")

        # Split right side on AND.
        rights = right.split(self.__class__.OP_AND)
        if '' in rights or right and not all(rights):
            raise GraphParseError(
                "null task name in graph: %s => %s" % (left, right))

        if not left or (self.__class__.OP_OR in left or '(' in left):
            # Treat conditional or bracketed expressions as a single entity.
            lefts = [left]
        else:
            # Split non-conditional left-side expressions on AND.
            lefts = left.split(self.__class__.OP_AND)
        if '' in lefts or left and not all(lefts):
            raise GraphParseError(
                "null task name in graph: %s => %s" % (left, right))

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
                if not trig and not name.startswith('@'):
                    # (Avoiding @trigger nodes.)
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
                if name.startswith('@'):
                    # (Avoiding @trigger nodes.)
                    continue
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
                            "bad family trigger in %s" % expr)
                    family_trig_map[(name, trig)] = (ttype, ext)
                else:
                    if (trig.endswith(self.__class__.FAM_TRIG_EXT_ANY) or
                            trig.endswith(self.__class__.FAM_TRIG_EXT_ALL)):
                        raise GraphParseError("family trigger on non-"
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

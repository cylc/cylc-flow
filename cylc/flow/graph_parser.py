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
"""Module for parsing cylc graph strings."""

import re
import contextlib

from cylc.flow.exceptions import GraphParseError
from cylc.flow.param_expand import GraphExpander
from cylc.flow.task_id import TaskID
from cylc.flow.task_trigger import TaskTrigger
from cylc.flow.task_outputs import (
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_FINISHED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED
)


class Replacement:
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


class GraphParser:
    """Class for extracting dependency information from cylc graph strings.

    For each task in the graph string, results are stored as:
        self.triggers[task_name][expression] = ([expr_task_names], suicide)
        self.original[task_name][expression] = original_expression

    (original_expression is separated out to allow comparison of triggers
    from different equivalent expressions, e.g. family vs member).

    This is currently intended to process a single multi-line graph string
    (i.e. the content of a single graph section). But it could be extended to
    store dependencies for the whole workflow (call parse_graph multiple times
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
            NODE(<PARAMS>)([CYCLE-POINT-OFFSET])(:TRIGGER)
        * The default trigger type is ':succeeded'.
        * A remote workflow qualified node name looks like this:
            NODE(<REMOTE-WORKFLOW-TRIGGER>)(:TRIGGER)
        * Outputs (boo:x) are ignored as triggers on the RHS to allow chaining:
            "foo => bar:x => baz & qux"
    """

    OP_AND = '&'
    OP_OR = '|'
    OP_AND_ERR = '&&'
    OP_OR_ERR = '||'
    SUICIDE = '!'
    OPTIONAL = '?'
    TRIGGER = ':'
    ARROW = '=>'
    ACTION = '@'

    TRIG_FAM_SUCCEED_ALL = "succeed-all"
    TRIG_FAM_SUCCEED_ANY = "succeed-any"
    TRIG_FAM_FAIL_ALL = "fail-all"
    TRIG_FAM_FAIL_ANY = "fail-any"
    TRIG_FAM_FINISH_ALL = "finish-all"
    TRIG_FAM_FINISH_ANY = "finish-any"
    TRIG_FAM_START_ALL = "start-all"
    TRIG_FAM_START_ANY = "start-any"
    TRIG_FAM_SUBMIT_ALL = "submit-all"
    TRIG_FAM_SUBMIT_ANY = "submit-any"
    TRIG_FAM_SUBMIT_FAIL_ALL = "submit-fail-all"
    TRIG_FAM_SUBMIT_FAIL_ANY = "submit-fail-any"

    # Map family trigger to inferred member output optionality.
    fam_output_map = {
        # Required outputs.
        # (started is never optional; only checked if task finishes)
        TRIG_FAM_START_ALL: (TASK_OUTPUT_STARTED, False),
        TRIG_FAM_START_ANY: (TASK_OUTPUT_STARTED, False),
        TRIG_FAM_SUCCEED_ALL: (TASK_OUTPUT_SUCCEEDED, False),
        TRIG_FAM_FAIL_ALL: (TASK_OUTPUT_FAILED, False),
        TRIG_FAM_SUBMIT_ALL: (TASK_OUTPUT_SUBMITTED, False),
        TRIG_FAM_SUBMIT_FAIL_ALL: (TASK_OUTPUT_SUBMIT_FAILED, False),
        # Optional outputs.
        TRIG_FAM_SUBMIT_FAIL_ANY: (TASK_OUTPUT_SUBMITTED, True),
        TRIG_FAM_SUCCEED_ANY: (TASK_OUTPUT_SUCCEEDED, True),
        TRIG_FAM_FAIL_ANY: (TASK_OUTPUT_SUCCEEDED, True),
        TRIG_FAM_FINISH_ALL: (TASK_OUTPUT_SUCCEEDED, True),
        TRIG_FAM_FINISH_ANY: (TASK_OUTPUT_SUCCEEDED, True),
        TRIG_FAM_SUBMIT_ANY: (TASK_OUTPUT_SUBMITTED, True),
    }

    # Map family trigger to member triggers. _ALL True, _ANY False
    fam_trigger_map = {
        TRIG_FAM_START_ALL: (TASK_OUTPUT_STARTED, True),
        TRIG_FAM_START_ANY: (TASK_OUTPUT_STARTED, False),
        TRIG_FAM_SUCCEED_ALL: (TASK_OUTPUT_SUCCEEDED, True),
        TRIG_FAM_SUCCEED_ANY: (TASK_OUTPUT_SUCCEEDED, False),
        TRIG_FAM_FAIL_ALL: (TASK_OUTPUT_FAILED, True),
        TRIG_FAM_FAIL_ANY: (TASK_OUTPUT_FAILED, False),
        TRIG_FAM_SUBMIT_ALL: (TASK_OUTPUT_SUBMITTED, True),
        TRIG_FAM_SUBMIT_ANY: (TASK_OUTPUT_SUBMITTED, False),
        TRIG_FAM_SUBMIT_FAIL_ALL: (TASK_OUTPUT_SUBMIT_FAILED, True),
        TRIG_FAM_SUBMIT_FAIL_ANY: (TASK_OUTPUT_SUBMITTED, False),
        TRIG_FAM_FINISH_ALL: (TASK_OUTPUT_FINISHED, True),
        TRIG_FAM_FINISH_ANY: (TASK_OUTPUT_FINISHED, False),
    }

    _RE_SUICIDE = r'(?:!)?'
    _RE_NODE = _RE_SUICIDE + TaskID.NAME_RE
    _RE_NODE_OR_ACTION = r'(?:[!@])?' + TaskID.NAME_RE
    _RE_PARAMS = r'<[\w,=\-+]+>'
    _RE_OFFSET = r'\[[\w\-\+\^:]+\]'
    _RE_TRIG = TRIGGER + r'[\w\-]+'  # task or fam trigger
    _RE_OPT = r'\??'  # optional output indicator

    # Match if there are any spaces which could lead to graph problems
    REC_GRAPH_BAD_SPACES_LINE = re.compile(
        TaskID.NAME_RE +
        r'''
        (?<![\-+](?=\s*[0-9]))  # allow spaces after -+ if numbers follow
        (?!\s*[\-+]\s*[0-9])    # allow spaces before/after -+ if nums follow
        \s+                     # do not allow 'task<space>task'
        ''' + TaskID.NAME_SUFFIX_RE, re.X)

    # Match @actions (xtriggers, and more to come?).
    REC_ACTION = re.compile(r'@[\w\-+%]+')

    # Match fully qualified parameterized single nodes.
    REC_NODE_FULL = re.compile(
        _RE_SUICIDE +
        r'''
        (?:(?:''' +
        TaskID.NAME_RE + r'(?:' + _RE_PARAMS + r')?|' + _RE_PARAMS +
        ''')                          # node name
        )+                            # allow task<param> to repeat
        (?:''' + _RE_OFFSET + r''')?  # optional cycle point offset
        (?:''' + _RE_TRIG + r''')?    # optional trigger
        (?:''' + _RE_OPT + r''')?     # optional optional indicator
        ''', re.X)                    # end of string

    # Extract node or action from left-side expressions after param expansion.
    REC_NODES = re.compile(r'''
        (''' + _RE_NODE_OR_ACTION + r''')  # node name
        (''' + _RE_OFFSET + r''')?         # optional cycle point offset
        (''' + _RE_TRIG + r''')?           # optional trigger
        (''' + _RE_OPT + r''')?            # optional optional indicator
    ''', re.X)

    REC_COMMENT = re.compile('#.*$')

    # Detect presence of expansion parameters in a graph line.
    REC_PARAMS = re.compile(_RE_PARAMS)

    # Detect and extract workflow state polling task info.
    REC_WORKFLOW_STATE = re.compile(
        r'(' + TaskID.NAME_RE + r''')
        (<([\w.\-/]+)::(''' + TaskID.NAME_RE + r''')
        (''' + _RE_TRIG + r')?>)',
        re.X
    )

    # Remove out-of-range nodes
    # <TASK_NAME_PART> : [^\s&\|] # i.e. sequence of not <AND|OR|SPACE>
    # <REMOVE_TOKEN>   : <TASK_NAME_PART> <_REMOVE>
    #                    <TASK_NAME_PART>?
    _TASK_NAME_PART = rf'[^\s{OP_AND}{OP_OR}]'
    _REMOVE_TOKEN = (rf'{_TASK_NAME_PART}+{str(GraphExpander._REMOVE)}?'
                     rf'{_TASK_NAME_PART}+')

    REC_NODE_OUT_OF_RANGE = re.compile(rf'''
        (                                     #
            ^{_REMOVE_TOKEN}[{OP_AND}{OP_OR}] # ^<REMOVE> <AND|OR>
            |                                 #
            [{OP_AND}{OP_OR}]{_REMOVE_TOKEN}  # <AND|OR> <REMOVE>
            |                                 #
            ^{_REMOVE_TOKEN}$                 # ^<REMOVE>$
        )                                     #
        ''', re.X)

    REC_RHS_NODE = re.compile(
        r'''
        (!)?                      # optional suicide mark
        (''' + _RE_NODE + r''')   # node name
        (''' + _RE_TRIG + r''')?  # optional trigger
        (''' + _RE_OPT + r''')?   # optional optional indicator
        ''',
        re.X
    )

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
        self.workflow_state_polling_tasks = {}
        self.task_output_opt = {}  # {(name, output): bool}
        self.memb_output_opt = {}  # {(name, output): bool}

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
            if i == 0 and this_line.startswith(self.__class__.ARROW):
                # First line can't start with an arrow.
                raise GraphParseError(f"Leading arrow: {this_line}")
            try:
                next_line = non_blank_lines[i + 1]
            except IndexError:
                next_line = ''
                if this_line.endswith(self.__class__.ARROW):
                    # Last line can't end with an arrow.
                    raise GraphParseError(
                        f"Trailing arrow: {this_line}")
            part_lines.append(this_line)
            if (
                this_line.endswith(self.__class__.ARROW) or
                next_line.startswith(self.__class__.ARROW)
            ):
                continue
            full_line = ''.join(part_lines)

            # Record inter-workflow dependence and remove the marker notation.
            # ("foo<WORKFLOW::TASK:fail> => bar" becomes:fail "foo => bar").
            repl = Replacement('\\1')
            full_line = self.__class__.REC_WORKFLOW_STATE.sub(repl, full_line)
            for item in repl.match_groups:
                l_task, r_all, r_workflow, r_task, r_status = item
                if r_status:
                    r_status = r_status.strip(self.__class__.TRIGGER)
                    r_status = TaskTrigger.standardise_name(r_status)
                else:
                    r_status = TASK_OUTPUT_SUCCEEDED
                self.workflow_state_polling_tasks[l_task] = (
                    r_workflow, r_task, r_status, r_all
                )
            full_lines.append(full_line)
            part_lines = []

        # Check for double-char conditional operators (a common mistake),
        # and bad node syntax (order of qualifiers).
        bad_lines = []
        for line in full_lines:
            if self.__class__.OP_AND_ERR in line:
                raise GraphParseError(
                    "The graph AND operator is "
                    f"'{self.__class__.OP_AND}': {line}")
            if self.__class__.OP_OR_ERR in line:
                raise GraphParseError(
                    "The graph OR operator is "
                    f"'{self.__class__.OP_OR}: {line}")
            # Check node syntax. First drop all non-node characters.
            node_str = line
            for spec in [
                self.__class__.ARROW,
                self.__class__.OP_OR,
                self.__class__.OP_AND,
                self.__class__.SUICIDE,
                '(',
                ')',
            ]:
                node_str = node_str.replace(spec, ' ')
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
            for line_ in graph_expander.expand(line):
                line_set.add(line_)

        # Process chains of dependencies as pairs: left => right.
        # Parameterization can duplicate some dependencies, so use a set.
        pairs = set()
        for line in line_set:
            chain = []
            # "foo => bar => baz" becomes [foo, bar, baz]
            # "foo => bar_-32768 => baz" becomes [foo]
            # "foo_-32768 => bar" becomes []
            for node in line.split(self.__class__.ARROW):
                # This can happen, e.g. "foo => => bar" produces
                # "foo, '', bar", so we add so that later it raises
                # an error
                if node == '':
                    chain.append(node)
                    continue
                node = self.REC_NODE_OUT_OF_RANGE.sub('', node)
                if node == '':
                    # For "foo => bar<err> => baz", stop at "bar<err>"
                    break
                else:
                    chain.append(node)

            if not chain:
                continue

            for item in self.__class__.REC_NODES.findall(chain[0]):
                # Auto-trigger lone nodes and initial nodes in a chain.
                if not item[0].startswith(self.__class__.ACTION):
                    pairs.add((None, ''.join(item)))

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
            " NAME(<PARAMS>)([CYCLE-POINT-OFFSET])(:TRIGGER)(?)\n"
            " {NAME(<PARAMS>) can also be: "
            "<PARAMS>NAME or NAME<PARAMS>NAME_CONTINUED}\n"
            " or\n"
            " NAME(<REMOTE-WORKFLOW-TRIGGER>)(:TRIGGER)")

    def _proc_dep_pair(self, left, right):
        """Process a single dependency pair 'left => right'.

        'left' can be a logical expression of qualified node names.
        'right' can be one or more node names joined by AND.
        A node is an xtrigger, or a task or a family name.
        A qualified name is NAME([CYCLE-POINT-OFFSET])(:TRIGGER).
        Trigger qualifiers, but not cycle offsets, are ignored on the right to
        allow chaining.
        """
        # Raise error for right-hand-side OR operators.
        if right and self.__class__.OP_OR in right:
            raise GraphParseError(f"Illegal OR on right side: {right}")

        # Raise error if suicide triggers on the left of the trigger.
        if left and self.__class__.SUICIDE in left:
            raise GraphParseError(
                "Suicide markers must be"
                f" on the right of a trigger: {left}")

        # Ignore cycle point offsets on the right side.
        # (Note we can't ban this; all nodes get process as left and right.)
        if right and '[' in right:
            return

        # Check that parentheses match.
        if left and left.count("(") != left.count(")"):
            raise GraphParseError(
                "Mismatched parentheses in: \"" + left + "\"")

        # Split right side on AND.
        rights = right.split(self.__class__.OP_AND)
        if '' in rights or right and not all(rights):
            raise GraphParseError(
                f"Null task name in graph: {left} => {right}")

        if not left or (self.__class__.OP_OR in left or '(' in left):
            # Treat conditional or bracketed expressions as a single entity.
            lefts = [left]
        else:
            # Split non-conditional left-side expressions on AND.
            lefts = left.split(self.__class__.OP_AND)
        if '' in lefts or left and not all(lefts):
            raise GraphParseError(
                f"Null task name in graph: {left} => {right}")

        for left in lefts:
            # Extract information about all nodes on the left.

            if left:
                info = self.__class__.REC_NODES.findall(left)
                expr = left

            else:
                # There is no left-hand-side task.
                info = []
                expr = ''

            n_info = []
            for name, offset, trig, opt_char in info:
                opt = opt_char == self.__class__.OPTIONAL
                if name.startswith(self.__class__.ACTION):
                    n_info.append((name, offset, trig, opt))
                    continue
                if trig:
                    # Replace with standard trigger name if necessary
                    trig = trig.strip(self.__class__.TRIGGER)
                    n_trig = TaskTrigger.standardise_name(trig)
                    if n_trig != trig:
                        if offset:
                            this = r'\b%s\b%s:%s(?!:)' % (
                                re.escape(name),
                                re.escape(offset),
                                re.escape(trig)
                            )
                        else:
                            this = r'\b%s:%s\b(?![\[:])' % (
                                re.escape(name),
                                re.escape(trig)
                            )
                        that = f"{name}{offset}:{n_trig}"
                        expr = re.sub(this, that, expr)
                else:
                    # Make success triggers explicit.
                    n_trig = TASK_OUTPUT_SUCCEEDED
                    if offset:
                        this = r'\b%s\b%s(?!:)' % (
                            re.escape(name),
                            re.escape(offset)
                        )
                    else:
                        this = r'\b%s\b(?![\[:])' % re.escape(name)
                    that = f"{name}{offset}:{n_trig}"
                    expr = re.sub(this, that, expr)

                n_info.append((name, offset, n_trig, opt))

            info = n_info

            # Determine semantics of all family triggers present.
            family_trig_map = {}
            for name, _, trig, _ in info:
                if name.startswith(self.__class__.ACTION):
                    # Avoid @trigger nodes.
                    continue
                if name in self.family_map:
                    # Family; deal with members
                    try:
                        family_trig_map[(name, trig)] = (
                            self.__class__.fam_trigger_map[trig]
                        )
                    except KeyError:
                        # Unqualified (FAM => foo) or bad (FAM:bad => foo).
                        raise GraphParseError(f"Bad family trigger in {expr}")
                else:
                    # Not family
                    if trig in self.__class__.fam_trigger_map:
                        raise GraphParseError("family trigger on non-"
                                              f"family namespace {expr}")

            # remove '?' from expr (not needed in logical trigger evaluation!)
            expr = re.sub(self.__class__._RE_OPT, '', expr)
            self._families_all_to_all(expr, rights, info, family_trig_map)

    def _families_all_to_all(self, expr, rights, info, family_trig_map):
        """Replace all family names with member names, for all/any semantics.

        (Also for graph segments with no family names.)
        """
        n_info = []
        n_expr = expr
        for name, offset, trig, _ in info:
            if (name, trig) in family_trig_map:
                ttype, mem_all = family_trig_map[(name, trig)]
                m_info = []
                m_expr = []
                for mem in self.family_map[name]:
                    m_info.append((mem, offset, ttype))
                    m_expr.append(f"{mem}{offset}:{ttype}")
                this = r'\b%s%s:%s\b' % (
                    name,
                    re.escape(offset),
                    trig
                )
                if mem_all:
                    that = '(%s)' % '&'.join(m_expr)
                else:
                    that = '(%s)' % '|'.join(m_expr)
                n_expr = re.sub(this, that, n_expr)
                n_info += m_info
            else:
                n_info += [(name, offset, trig)]

        self._compute_triggers(expr, rights, n_expr, n_info)

    def _set_triggers(
        self, output_map, name, output, optional, suicide, trigs, expr,
        orig_expr, family=False
    ):
        """Record parsed triggers and outputs."""
        # TODO CAN WE RETURN IF expr == "" HERE?

        # Check suicide triggers
        with contextlib.suppress(KeyError):
            osuicide = self.triggers[name][expr][1]
            # This trigger already exists, so we must have both
            # "expr => member" and "expr => !member" in the graph,
            # or simply a duplicate trigger not recognized earlier
            # because of parameter offsets.
            if not expr:
                pass
            elif suicide is not osuicide:
                oexp = re.sub(r'(&|\|)', r' \1 ', orig_expr)
                oexp = re.sub(r':succeeded', '', oexp)
                raise GraphParseError(
                    f"{oexp} can't trigger both {name} and !{name}"
                )

        # Record triggers
        self.triggers.setdefault(name, {})
        self.triggers[name][expr] = (trigs, suicide)
        self.original.setdefault(name, {})
        self.original[name][expr] = orig_expr

        if family and output == "" or suicide:
            # Do not infer output optionality from suicide triggers
            # or from a family name on the right side.
            return

        # Add or check {(name, output): optional} in output_map.
        try:
            already = output_map[(name, output)]
        except KeyError:
            # Not already in map; add it.
            output_map[(name, output)] = optional
        else:
            # Already in map; check consistency with previous value,
            if already != optional:
                if not family:
                    raise GraphParseError(
                        f"{name}:{output} can't be both optional and required"
                    )
                else:
                    output_map[(name, output)] = True

    def _compute_triggers(self, orig_expr, rights, expr, info):
        """Store trigger info from "expr => right".

        info: [(name, offset, trigger_type)] for each name in expr.
        rights: include qualifiers like foo? and foo:fail?
        """
        trigs = []
        for name, offset, trigger in info:
            # Replace finish triggers (must be done after member substn).
            if name.startswith(self.__class__.ACTION):
                trigs += [name]
            elif trigger == TASK_OUTPUT_FINISHED:
                this = f"{name}{offset}:{trigger}"
                that = "(%s%s:%s%s%s%s:%s)" % (
                    name, offset, TASK_OUTPUT_SUCCEEDED,
                    self.__class__.OP_OR,
                    name, offset, TASK_OUTPUT_FAILED)
                expr = expr.replace(this, that)
                trigs += [
                    "%s%s:%s" % (name, offset, TASK_OUTPUT_SUCCEEDED),
                    "%s%s:%s" % (name, offset, TASK_OUTPUT_FAILED)]
            else:
                trigs += [f"{name}{offset}:{trigger}"]

        for right in rights:
            m = self.__class__.REC_RHS_NODE.match(right)
            if not m:
                raise GraphParseError(f"Illegal graph node: {right}")
            suicide_char, name, output, opt_char = m.groups()
            suicide = (suicide_char == self.__class__.SUICIDE)
            opt = opt_char == self.__class__.OPTIONAL
            if output:
                output = output.strip(self.__class__.TRIGGER)

            if name not in self.family_map:
                # Task.
                if output:
                    output = TaskTrigger.standardise_name(output)
                else:
                    # Make implicit success case explicit.
                    output = TASK_OUTPUT_SUCCEEDED

                self._set_triggers(
                    self.task_output_opt, name, output, opt,
                    suicide, trigs, expr, orig_expr
                )
            else:
                # Family.
                if opt:
                    raise GraphParseError(
                        "Family triggers can't be optional: "
                        f"{name}:{output}{self.__class__.OPTIONAL}"
                    )

                # Derive member optional/required outputs.
                try:
                    output, optional = self.__class__.fam_output_map[output]
                except KeyError:
                    if output:
                        raise GraphParseError(
                            f"Illegal family trigger: {name}:{output}"
                        )
                    # Unqualified family on the right implies nothing
                    # about outputs
                    optional = None

                for member in self.family_map[name]:
                    # Expand to family members.
                    self._set_triggers(
                        self.memb_output_opt, member, output, optional,
                        suicide, trigs, expr, orig_expr, family=True
                    )

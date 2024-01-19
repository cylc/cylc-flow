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

from typing import (
    Set,
    Dict,
    List,
    Tuple,
    Optional,
    Union
)

import cylc.flow.flags
from cylc.flow.exceptions import GraphParseError
from cylc.flow.param_expand import GraphExpander
from cylc.flow.task_id import TaskID
from cylc.flow.task_trigger import TaskTrigger
from cylc.flow.task_outputs import (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_FINISHED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED
)
from cylc.flow.task_qualifiers import (
    QUAL_FAM_EXPIRE_ALL,
    QUAL_FAM_EXPIRE_ANY,
    QUAL_FAM_SUCCEED_ALL,
    QUAL_FAM_SUCCEED_ANY,
    QUAL_FAM_FAIL_ALL,
    QUAL_FAM_FAIL_ANY,
    QUAL_FAM_FINISH_ALL,
    QUAL_FAM_FINISH_ANY,
    QUAL_FAM_START_ALL,
    QUAL_FAM_START_ANY,
    QUAL_FAM_SUBMIT_ALL,
    QUAL_FAM_SUBMIT_ANY,
    QUAL_FAM_SUBMIT_FAIL_ALL,
    QUAL_FAM_SUBMIT_FAIL_ANY,
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

    The general form of a dependency is "LHS => RHS", where:
        * On the left, an EXPRESSION of nodes involving parentheses, and
          logical operators '&' (AND), and '|' (OR).
        * On the right, an EXPRESSION of nodes NOT involving '|'
        * Node names may be parameterized (any number of parameters):
            NODE<i,j,k>
            NODE<i=0,j,k>  # specific parameter value
            NODE<i-1,j,k>  # offset parameter value
        * A parameterized qualified node name looks like this:
            NODE(<PARAMS>)([CYCLE-POINT-OFFSET])(:QUALIFIER)
        * The default trigger type is ':succeeded'.
        * A remote workflow qualified node name looks like this:
            NODE(<REMOTE-WORKFLOW-QUALIFIER>)(:QUALIFIER)
        * Outputs (boo:x) are ignored as triggers on the RHS to allow chaining:
            "foo => bar:x => baz & qux"
    """

    CYLC7_COMPAT = "CYLC 7 BACK-COMPAT"

    OP_AND = '&'
    OP_OR = '|'
    OP_AND_ERR = '&&'
    OP_OR_ERR = '||'
    SUICIDE = '!'
    OPTIONAL = '?'
    QUALIFIER = ':'
    ARROW = '=>'
    XTRIG = '@'
    CONTINUATION_STRS = (ARROW, OP_AND, OP_OR)
    BAD_STRS = (OP_AND_ERR, OP_OR_ERR)

    # Map family trigger type to (member-trigger, any/all), for use in
    # expanding family trigger expressions to member trigger expressions.
    # - "FAM:succeed-all => g" means "f1:succeed & f2:succeed => g"
    # - "FAM:fail-any => g" means "f1:fail | f2:fail => g".
    # E.g. QUAL_FAM_START_ALL: (TASK_OUTPUT_STARTED, True) simply maps
    #   "FAM:start-all" to "MEMBER:started" and "-all" (all members).
    fam_to_mem_trigger_map: Dict[str, Tuple[str, bool]] = {
        QUAL_FAM_EXPIRE_ALL: (TASK_OUTPUT_EXPIRED, True),
        QUAL_FAM_EXPIRE_ANY: (TASK_OUTPUT_EXPIRED, False),
        QUAL_FAM_START_ALL: (TASK_OUTPUT_STARTED, True),
        QUAL_FAM_START_ANY: (TASK_OUTPUT_STARTED, False),
        QUAL_FAM_SUCCEED_ALL: (TASK_OUTPUT_SUCCEEDED, True),
        QUAL_FAM_SUCCEED_ANY: (TASK_OUTPUT_SUCCEEDED, False),
        QUAL_FAM_FAIL_ALL: (TASK_OUTPUT_FAILED, True),
        QUAL_FAM_FAIL_ANY: (TASK_OUTPUT_FAILED, False),
        QUAL_FAM_SUBMIT_ALL: (TASK_OUTPUT_SUBMITTED, True),
        QUAL_FAM_SUBMIT_ANY: (TASK_OUTPUT_SUBMITTED, False),
        QUAL_FAM_SUBMIT_FAIL_ALL: (TASK_OUTPUT_SUBMIT_FAILED, True),
        QUAL_FAM_SUBMIT_FAIL_ANY: (TASK_OUTPUT_SUBMITTED, False),
        QUAL_FAM_FINISH_ALL: (TASK_OUTPUT_FINISHED, True),
        QUAL_FAM_FINISH_ANY: (TASK_OUTPUT_FINISHED, False),
    }

    # Map family pseudo triggers to affected member outputs.
    fam_to_mem_output_map: Dict[str, List[str]] = {
        QUAL_FAM_EXPIRE_ANY: [TASK_OUTPUT_EXPIRED],
        QUAL_FAM_EXPIRE_ALL: [TASK_OUTPUT_EXPIRED],
        QUAL_FAM_START_ANY: [TASK_OUTPUT_STARTED],
        QUAL_FAM_START_ALL: [TASK_OUTPUT_STARTED],
        QUAL_FAM_SUCCEED_ANY: [TASK_OUTPUT_SUCCEEDED],
        QUAL_FAM_SUCCEED_ALL: [TASK_OUTPUT_SUCCEEDED],
        QUAL_FAM_FAIL_ANY: [TASK_OUTPUT_FAILED],
        QUAL_FAM_FAIL_ALL: [TASK_OUTPUT_FAILED],
        QUAL_FAM_SUBMIT_ANY: [TASK_OUTPUT_SUBMITTED],
        QUAL_FAM_SUBMIT_ALL: [TASK_OUTPUT_SUBMITTED],
        QUAL_FAM_SUBMIT_FAIL_ANY: [TASK_OUTPUT_SUBMIT_FAILED],
        QUAL_FAM_SUBMIT_FAIL_ALL: [TASK_OUTPUT_SUBMIT_FAILED],
        QUAL_FAM_FINISH_ANY: [TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED],
        QUAL_FAM_FINISH_ALL: [TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED]
    }

    _RE_SUICIDE = r'(?:!)?'
    _RE_NODE = _RE_SUICIDE + TaskID.NAME_RE
    _RE_NODE_OR_XTRIG = r'(?:[!@])?' + TaskID.NAME_RE
    _RE_PARAMS = r'<[\w,=\-+]+>'
    _RE_OFFSET = r'\[[\w\-\+\^:]+\]'
    _RE_QUAL = QUALIFIER + r'[\w\-]+'  # task or fam trigger
    _RE_OPT = r'\??'  # optional output indicator

    REC_QUAL = re.compile(_RE_QUAL)

    # Match if there are any spaces which could lead to graph problems
    REC_GRAPH_BAD_SPACES_LINE = re.compile(
        TaskID.NAME_RE +
        rf"""
        (?<![\-+](?=\s*[0-9]))  # allow spaces after -+ if numbers follow
        (?!\s*[\-+]\s*[0-9])    # allow spaces before/after -+ if nums follow
        \s+                     # do not allow 'task<space>task'
        {TaskID.NAME_SUFFIX_RE}
        """,
        re.X
    )

    # Match @xtriggers.
    REC_XTRIG = re.compile(r'@[\w\-+%]+')

    # Match fully qualified parameterized single nodes.
    REC_NODE_FULL = re.compile(
        rf"""
        {_RE_SUICIDE}
        (?:(?:{TaskID.NAME_RE}             # node name
        (?:{_RE_PARAMS})?|{_RE_PARAMS}))+  # allow task<param> to repeat
        (?:{_RE_OFFSET})?                  # cycle point offset
        (?:{_RE_QUAL})?                    # qualifier
        (?:{_RE_OPT})?                     # optional output indicator
        """,
        re.X
    )

    # Extract node or xtrigger from LHS expressions after param expansion.
    REC_NODES = re.compile(
        rf"""
        ({_RE_NODE_OR_XTRIG})  # node name
        ({_RE_OFFSET})?        # cycle point offset
        ({_RE_QUAL})?          # trigger qualifier
        ({_RE_OPT})?           # optional output indicator
        """,
        re.X
    )

    REC_COMMENT = re.compile('#.*$')

    # Detect presence of expansion parameters in a graph line.
    REC_PARAMS = re.compile(_RE_PARAMS)

    # Detect and extract workflow state polling task info.
    REC_WORKFLOW_STATE = re.compile(
        rf"""
        ({TaskID.NAME_RE})
        (<([\w.\-/]+)::({TaskID.NAME_RE})
        ({_RE_QUAL})?>)
        """,
        re.X
    )

    # Remove out-of-range nodes
    # <TASK_NAME_PART> : [^\s&\|] # i.e. sequence of not <AND|OR|SPACE>
    # <REMOVE_TOKEN>   : <TASK_NAME_PART> <_REMOVE>
    #                    <TASK_NAME_PART>?
    _TASK_NAME_PART = rf'[^\s{OP_AND}{OP_OR}]'
    _REMOVE_TOKEN = (
        rf"{_TASK_NAME_PART}+{str(GraphExpander._REMOVE)}?{_TASK_NAME_PART}+"
    )

    REC_NODE_OUT_OF_RANGE = re.compile(
        rf"""
        (                                     #
            ^{_REMOVE_TOKEN}[{OP_AND}{OP_OR}] # ^<REMOVE> <AND|OR>
            |                                 #
            [{OP_AND}{OP_OR}]{_REMOVE_TOKEN}  # <AND|OR> <REMOVE>
            |                                 #
            ^{_REMOVE_TOKEN}$                 # ^<REMOVE>$
        )                                     #
        """,
        re.X
    )

    REC_RHS_NODE = re.compile(
        rf"""
        (!)?           # suicide mark
        ({_RE_NODE})   # node name
        ({_RE_QUAL})?  # trigger qualifier
        ({_RE_OPT})?   # optional output indicator
        """,
        re.X
    )

    def __init__(
        self,
        family_map: Optional[Dict[str, List[str]]] = None,
        parameters: Optional[Dict] = None,
        task_output_opt:
            Optional[Dict[Tuple[str, str], Tuple[bool, bool, bool]]] = None
    ) -> None:
        """Initialize the graph string parser.

        Args:
            family_map:
                {family_name: [family member task names]}
            parameters:
                task parameters for expansion here
            task_output_opt:
                {(name, output): (is-optional, is-opt-default, is-fixed)}
                passed in to allow checking across multiple graph strings

        """
        self.family_map = family_map or {}
        self.parameters = parameters
        self.triggers: Dict = {}
        self.original: Dict = {}
        self.workflow_state_polling_tasks: Dict = {}

        # Record task outputs as optional or required:
        #   {(name, output): (is_optional, is_member)}
        # (Need to compare across separately-parsed graph strings.)
        if task_output_opt:
            self.task_output_opt = task_output_opt
        else:
            self.task_output_opt = {}

    def parse_graph(self, graph_string: str) -> None:
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
            for seq in self.CONTINUATION_STRS:
                if i == 0 and this_line.startswith(seq):
                    # First line can't start with an arrow.
                    raise GraphParseError(f"Leading {seq}: {this_line}")
            try:
                next_line = non_blank_lines[i + 1]
            except IndexError:
                next_line = ''
                for seq in self.CONTINUATION_STRS:
                    if this_line.endswith(seq):
                        # Last line can't end with an arrow, & or |.
                        raise GraphParseError(
                            f"Dangling {seq}:"
                            f"{this_line}"
                        )
            part_lines.append(this_line)

            # Check that a continuation sequence doesn't end this line and
            # begin the next:
            if (
                this_line.endswith(self.CONTINUATION_STRS) and
                next_line.startswith(self.CONTINUATION_STRS)
            ):
                raise GraphParseError(
                    'Consecutive lines end and start with continuation '
                    'characters:\n'
                    f'{this_line}\n'
                    f'{next_line}'
                )

            # Check that line ends with a valid continuation sequence:
            if (any(
                this_line.endswith(seq) or next_line.startswith(seq) for
                seq in self.CONTINUATION_STRS
            ) and not (any(
                this_line.endswith(seq) or next_line.startswith(seq) for
                seq in self.BAD_STRS
            ))):
                continue

            full_line = ''.join(part_lines)

            # Record inter-workflow dependence and remove the marker notation.
            # ("foo<WORKFLOW::TASK:fail> => bar" becomes:fail "foo => bar").
            repl = Replacement('\\1')
            full_line = self.__class__.REC_WORKFLOW_STATE.sub(repl, full_line)
            for item in repl.match_groups:
                l_task, r_all, r_workflow, r_task, r_status = item
                if r_status:
                    r_status = r_status.strip(self.__class__.QUALIFIER)
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
                    f"'{self.__class__.OP_OR}': {line}")
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
            # Drop all valid @xtriggers, longest first to avoid sub-strings.
            nodes = self.__class__.REC_XTRIG.findall(node_str)
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
        pairs: Set[Tuple[Optional[str], str]] = set()
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
                if not item[0].startswith(self.__class__.XTRIG):
                    pairs.add((None, ''.join(item)))

            for i in range(0, len(chain) - 1):
                pairs.add((chain[i], chain[i + 1]))

        for pair in pairs:
            self._proc_dep_pair(pair)

    @classmethod
    def _report_invalid_lines(cls, lines: List[str]) -> None:
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
            "Bad graph node format:\n"
            "  " + "\n  ".join(lines) + "\n"
            "Correct format is:\n"
            " @XTRIG or "
            " NAME(<PARAMS>)([CYCLE-POINT-OFFSET])(:QUALIFIER)(?)\n"
            " {NAME(<PARAMS>) can also be: "
            "<PARAMS>NAME or NAME<PARAMS>NAME_CONTINUED}\n"
            " or\n"
            " NAME(<REMOTE-WORKFLOW-QUALIFIER>)(:QUALIFIER)")

    def _proc_dep_pair(
        self,
        pair: Tuple[Optional[str], str]
    ) -> None:
        """Process a single dependency pair 'left => right'.

        'left' can be a logical expression of qualified node names.
        'left' can be None, when triggering a left-side or lone node.
        'left' can be "", if null task name in graph error (a => => b).
        'right' can be one or more node names joined by AND.
        'right' can't be None or "".
        A node is an xtrigger, or a task or a family name.
        A qualified name is NAME([CYCLE-POINT-OFFSET])(:QUALIFIER).
        Trigger qualifiers, but not cycle offsets, are ignored on the right to
        allow chaining.
        """
        left, right = pair
        # Raise error for right-hand-side OR operators.
        if self.__class__.OP_OR in right:
            raise GraphParseError(f"Illegal OR on right side: {right}")

        # Raise error if suicide triggers on the left of the trigger.
        if left and self.__class__.SUICIDE in left:
            raise GraphParseError(
                "Suicide markers must be"
                f" on the right of a trigger: {left}")

        # Check that parentheses match.
        mismatch_msg = 'Mismatched parentheses in: "{}"'
        if left and left.count("(") != left.count(")"):
            raise GraphParseError(mismatch_msg.format(left))
        if right.count("(") != right.count(")"):
            raise GraphParseError(mismatch_msg.format(right))

        # Ignore cycle point offsets on the right side.
        # (Note we can't ban this; all nodes get process as left and right.)
        if '[' in right:
            return

        # Split right side on AND.
        rights = right.split(self.__class__.OP_AND)
        if '' in rights or right and not all(rights):
            raise GraphParseError(
                f"Null task name in graph: {left} => {right}")

        lefts: Union[List[str], List[Optional[str]]]
        if not left or (self.__class__.OP_OR in left or '(' in left):
            # Treat conditional or parenthesised expressions as a single entity
            # Can get [None] or [""] here
            lefts = [left]
        else:
            # Split non-conditional left-side expressions on AND.
            # Can get [""] here too
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

            n_info: List[Tuple[str, str, str, bool]] = []
            for name, offset, trig, opt_char in info:
                opt = opt_char == self.__class__.OPTIONAL
                if name.startswith(self.__class__.XTRIG):
                    n_info.append((name, offset, trig, opt))
                    continue
                if trig:
                    # Replace with standard trigger name if necessary
                    trig = trig.strip(self.__class__.QUALIFIER)
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
                if name.startswith(self.__class__.XTRIG):
                    # Avoid @xtrigger nodes.
                    continue
                if name in self.family_map:
                    # Family; deal with members.
                    try:
                        family_trig_map[(name, trig)] = (
                            self.__class__.fam_to_mem_trigger_map[trig]
                        )
                    except KeyError:
                        # "FAM:bad => foo" in LHS (includes "FAM => bar" too).
                        raise GraphParseError(
                            f"Illegal family trigger in {expr}")
                else:
                    # Not a family.
                    if trig in self.__class__.fam_to_mem_trigger_map:
                        raise GraphParseError(
                            "family trigger on non-family namespace {expr}")

            # remove '?' from expr (not needed in logical trigger evaluation)
            expr = re.sub(self.__class__._RE_OPT, '', expr)
            self._families_all_to_all(expr, rights, info, family_trig_map)

    def _families_all_to_all(
        self,
        expr: str,
        rights: List[str],
        info: List[Tuple[str, str, str, bool]],
        family_trig_map: Dict[Tuple[str, str], Tuple[str, bool]]
    ) -> None:
        """Replace all family names with member names, for all/any semantics.

        Args:
            expr: the associated graph expression
            rights: list of right-side nodes
            trigs: parsed trigger info
            info: [(name, offset, trigger-name, optional)] for each node
            expr: the associated graph expression for this graph line

        """
        # Process left-side expression for defining triggers.
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
        self,
        name: str,
        suicide: bool,
        trigs: List[str],
        expr: str,
        orig_expr: str
    ) -> None:
        """Record parsed triggers.

        Args:
            name: task name
            suicide: whether this is a suicide trigger or not
            trigs: parsed trigger info
            expr: the associated graph expression
            orig_expr: the original associated graph expression
        """

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
                    f"{oexp} can't trigger both {name} and !{name}")

        # Record triggers
        self.triggers.setdefault(name, {})
        self.triggers[name][expr] = (trigs, suicide)
        self.original.setdefault(name, {})
        self.original[name][expr] = orig_expr

    def _set_output_opt(
        self,
        name: str,
        output: str,
        optional: bool,
        suicide: bool,
        fam_member: bool = False
    ) -> None:
        """Set or check consistency of optional/required output.

        Args:
            name: task name
            output: task output name
            optional: is the output optional?
            suicide: is this from a suicide trigger?
            fam_member: is this from an expanded family trigger?

        """
        if cylc.flow.flags.cylc7_back_compat:
            # Set all outputs optional (set :succeed required elsewhere).
            self.task_output_opt[(name, output)] = (True, True, True)
            return

        # Do not infer output optionality from suicide triggers:
        if suicide:
            return

        if output == TASK_OUTPUT_FINISHED:
            # Interpret :finish pseudo-output
            if optional:
                raise GraphParseError(
                    f"Pseudo-output {name}:{output} can't be optional")
            # But implicit optional for the real succeed/fail outputs.
            optional = True
            for outp in [TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED]:
                self._set_output_opt(
                    name, outp, optional, suicide, fam_member)

        try:
            prev_optional, prev_default, prev_fixed = (
                self.task_output_opt[(name, output)])
        except KeyError:
            # Not already set; set it. Fix it if not fam_member.
            self.task_output_opt[(name, output)] = (
                optional, optional, not fam_member)
        else:
            # Already set; check consistency with previous.
            if prev_fixed:
                # optionality fixed already
                if fam_member:
                    pass
                else:
                    if optional != prev_optional:
                        raise GraphParseError(
                            f"Output {name}:{output} can't be both required"
                            " and optional")
            else:
                # optionality not fixed yet (only family default)
                if fam_member:
                    # family defaults must be consistent
                    if optional != prev_default:
                        raise GraphParseError(
                            f"Output {name}:{output} can't default to both"
                            " optional and required (via family trigger"
                            " defaults)")
                else:
                    # fix the optionality now
                    self.task_output_opt[(name, output)] = (
                        optional, prev_default, True)

        # Check opposite output where appropriate.
        for opposites in [
            (TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED),
            (TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_SUBMIT_FAILED)
        ]:
            if output not in opposites:
                continue
            succeed, fail = opposites
            opposite = fail if output == succeed else succeed
            try:
                opp_optional, opp_default, opp_fixed = (
                    self.task_output_opt[(name, opposite)]
                )
            except KeyError:
                # opposite not set, no need to check
                continue
            else:
                # opposite already set; check consistency
                optional, default, oset = (
                    self.task_output_opt[(name, output)]
                )
                msg = (f"Opposite outputs {name}:{output} and {name}:"
                       f"{opposite} must both be optional if both are used")
                if fam_member or not opp_fixed:
                    if not optional or not opp_default:
                        raise GraphParseError(
                            msg + " (via family trigger defaults)")
                    elif not optional or not opp_optional:
                        raise GraphParseError(
                            msg + " (via family trigger)")
                elif not optional or not opp_optional:
                    raise GraphParseError(msg)

    def _compute_triggers(
        self,
        orig_expr: str,
        rights: List[str],
        expr: str,
        info: List[Tuple[str, str, str]]
    ) -> None:
        """Store trigger info from "expr => right".

        Args:
            orig_expr: the original associated graph expression
            rights: list of right-side nodes including qualifiers like :fail?
            expr: the associated graph expression
            info: [(name, offset, trigger-name)] for each name in expr.

        """
        trigs = []
        for name, offset, trigger in info:
            # Replace finish triggers (must be done after member substn).
            if name.startswith(self.__class__.XTRIG):
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
            right = right.strip('()')  # parentheses don't matter
            m = self.__class__.REC_RHS_NODE.match(right)
            if not m:
                # Bad nodes should have been detected earlier; fail loudly
                raise ValueError(  # pragma: no cover
                    f"Unexpected graph expression: '{right}'"
                )
            suicide_char, name, output, opt_char = m.groups()
            suicide = (suicide_char == self.__class__.SUICIDE)
            optional = (opt_char == self.__class__.OPTIONAL)
            if output:
                output = output.strip(self.__class__.QUALIFIER)

            if name in self.family_map:
                fam = True
                mems = self.family_map[name]
                if not output:
                    # (Plain family name on RHS).
                    # Make implicit success explicit.
                    output = QUAL_FAM_SUCCEED_ALL
                elif output.startswith("finish"):
                    if optional:
                        raise GraphParseError(
                            f"Family pseudo-output {name}:{output} can't be"
                            " optional")
                    # But implicit optional for the real succeed/fail outputs.
                    optional = True
                try:
                    outputs = self.__class__.fam_to_mem_output_map[output]
                except KeyError:
                    # Illegal family trigger on RHS of a pair.
                    raise GraphParseError(
                        f"Illegal family trigger: {name}:{output}")
            else:
                fam = False
                if not output:
                    # Make implicit success explicit.
                    output = TASK_OUTPUT_SUCCEEDED
                else:
                    # Convert to standard output names if necessary.
                    output = TaskTrigger.standardise_name(output)
                mems = [name]
                outputs = [output]

            for mem in mems:
                self._set_triggers(mem, suicide, trigs, expr, orig_expr)
                for output in outputs:
                    self._set_output_opt(mem, output, optional, suicide, fam)

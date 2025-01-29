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
"""Task output message manager and constants."""

import ast
import re
from typing import (
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    TYPE_CHECKING,
    Tuple,
    Union,
)

from cylc.flow.exceptions import InvalidCompletionExpression
from cylc.flow.util import (
    BOOL_SYMBOLS,
    get_variable_names,
    restricted_evaluator,
)

if TYPE_CHECKING:
    from cylc.flow.taskdef import TaskDef
    from typing_extensions import Literal


# Standard task output strings, used for triggering.
TASK_OUTPUT_EXPIRED = "expired"
TASK_OUTPUT_SUBMITTED = "submitted"
TASK_OUTPUT_SUBMIT_FAILED = "submit-failed"
TASK_OUTPUT_STARTED = "started"
TASK_OUTPUT_SUCCEEDED = "succeeded"
TASK_OUTPUT_FAILED = "failed"
TASK_OUTPUT_FINISHED = "finished"

SORT_ORDERS = (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED,
)

TASK_OUTPUTS = (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_FINISHED,
)

# DB output message for forced completion
FORCED_COMPLETION_MSG = "(manually completed)"

# this evaluates task completion expressions
CompletionEvaluator = restricted_evaluator(
    # expressions
    ast.Expression,
    # variables
    ast.Name, ast.Load,
    # operations
    ast.BoolOp, ast.And, ast.Or, ast.BinOp,
    error_class=InvalidCompletionExpression,
)

# regex for splitting expressions into individual parts for formatting
RE_EXPR_SPLIT = re.compile(r'([\(\) ])')


def trigger_to_completion_variable(output: str) -> str:
    """Turn a trigger into something that can be used in an expression.

    Examples:
        >>> trigger_to_completion_variable('succeeded')
        'succeeded'
        >>> trigger_to_completion_variable('submit-failed')
        'submit_failed'

    """
    return output.replace('-', '_')


def get_trigger_completion_variable_maps(triggers: Iterable[str]):
    """Return a bi-map of trigger to completion variable.

    Args:
        triggers: All triggers for a task.

    Returns:
        (trigger_to_completion_variable, completion_variable_to_trigger)

        Tuple of mappings for converting in either direction.

    """
    _trigger_to_completion_variable = {}
    _completion_variable_to_trigger = {}
    for trigger in triggers:
        compvar = trigger_to_completion_variable(trigger)
        _trigger_to_completion_variable[trigger] = compvar
        _completion_variable_to_trigger[compvar] = trigger

    return (
        _trigger_to_completion_variable,
        _completion_variable_to_trigger,
    )


def get_completion_expression(tdef: 'TaskDef') -> str:
    """Return a completion expression for this task definition.

    If there is *not* a user provided completion statement:

    1. Create a completion expression that ensures all required ouputs are
       completed.
    2. If success is optional add "or succeeded or failed" onto the end.
    3. If submission is optional add "or submit-failed" onto the end of it.
    4. If expiry is optional add "or expired" onto the end of it.
    """
    # check if there is a user-configured completion expression
    completion = tdef.rtconfig.get('completion')
    if completion:
        # completion expression is defined in the runtime -> return it
        return completion

    # (1) start with an expression that ensures all required outputs are
    # generated (if the task runs)
    required = {
        trigger_to_completion_variable(trigger)
        for trigger, (_message, required) in tdef.outputs.items()
        if required
    }
    parts = []
    if required:
        _part = ' and '.join(sorted(required))
        if len(required) > 1:
            # wrap the expression in brackets for clarity
            parts.append(f'({_part})')
        else:
            parts.append(_part)

    # (2) handle optional success
    if (
        tdef.outputs[TASK_OUTPUT_SUCCEEDED][1] is False
        or tdef.outputs[TASK_OUTPUT_FAILED][1] is False
    ):
        # failure is tolerated -> ensure the task succeeds OR fails
        if required:
            # required outputs are required only if the task actually runs
            parts = [
                f'({parts[0]} and {TASK_OUTPUT_SUCCEEDED})'
                f' or {TASK_OUTPUT_FAILED}'
            ]
        else:
            parts.append(
                f'{TASK_OUTPUT_SUCCEEDED} or {TASK_OUTPUT_FAILED}'
            )

    # (3) handle optional submission
    if (
        tdef.outputs[TASK_OUTPUT_SUBMITTED][1] is False
        or tdef.outputs[TASK_OUTPUT_SUBMIT_FAILED][1] is False
    ):
        # submit-fail tolerated -> ensure the task executes OR submit-fails
        parts.append(
            trigger_to_completion_variable(TASK_OUTPUT_SUBMIT_FAILED)
        )

    # (4) handle optional expiry
    if tdef.outputs[TASK_OUTPUT_EXPIRED][1] is False:
        # expiry tolerated -> ensure the task executes OR expires
        parts.append(TASK_OUTPUT_EXPIRED)

    return ' or '.join(parts)


def get_optional_outputs(
    expression: str,
    outputs: Iterable[str],
    disable: "Optional[str]" = None
) -> Dict[str, Optional[bool]]:
    """Determine which outputs in an expression are optional.

    Args:
        expression:
            The completion expression.
        outputs:
            All outputs that apply to this task.
        disable:
            Disable this output and any others it is joined with by `and`
            (which will mean they are necessarily optional).

    Returns:
        dict: compvar: is_optional

        compvar:
            The completion variable, i.e. the trigger as used in the completion
            expression.
        is_optional:
            * True if var is optional.
            * False if var is required.
            * None if var is not referenced.

    Examples:
        >>> sorted(get_optional_outputs(
        ...     '(succeeded and (x or y)) or failed',
        ...     {'succeeded', 'x', 'y', 'failed', 'expired'}
        ... ).items())
        [('expired', None), ('failed', True), ('succeeded', True),
         ('x', True), ('y', True)]

        >>> sorted(get_optional_outputs(
        ...     '(succeeded and x and y) or expired',
        ...     {'succeeded', 'x', 'y', 'failed', 'expired'}
        ... ).items())
        [('expired', True), ('failed', None), ('succeeded', False),
         ('x', False), ('y', False)]

        >>> sorted(get_optional_outputs(
        ...     '(succeeded and towel) or (failed and bugblatter)',
        ...     {'succeeded', 'towel', 'failed', 'bugblatter'},
        ... ).items())
        [('bugblatter', True), ('failed', True),
         ('succeeded', True), ('towel', True)]

        >>> sorted(get_optional_outputs(
        ...     '(succeeded and towel) or (failed and bugblatter)',
        ...     {'succeeded', 'towel', 'failed', 'bugblatter'},
        ...     disable='failed'
        ... ).items())
        [('bugblatter', True), ('failed', True),
         ('succeeded', False), ('towel', False)]

    """
    # determine which triggers are used in the expression
    used_compvars = get_variable_names(expression)

    # all completion variables which could appear in the expression
    all_compvars = {trigger_to_completion_variable(out) for out in outputs}

    # Allows exclusion of additional outcomes:
    extra_excludes = {disable: False} if disable else {}

    return {  # output: is_optional
        # the outputs that are used in the expression
        **{
            output: CompletionEvaluator(
                expression,
                **{
                    **{out: out != output for out in all_compvars},
                    # don't consider pre-execution conditions as optional
                    # (pre-conditions are considered separately)
                    'expired': False,
                    'submit_failed': False,
                    **extra_excludes
                },
            )
            for output in used_compvars
        },
        **dict.fromkeys(all_compvars - used_compvars),
    }


# a completion expression that considers the outputs complete if any final task
# output is received
FINAL_OUTPUT_COMPLETION = ' or '.join(
    map(
        trigger_to_completion_variable,
        [
            TASK_OUTPUT_SUCCEEDED,
            TASK_OUTPUT_FAILED,
            TASK_OUTPUT_SUBMIT_FAILED,
            TASK_OUTPUT_EXPIRED,
        ],
    )
)


class TaskOutputs:
    """Represents a collection of outputs for a task.

    Task outputs have a trigger and a message:
    * The trigger is used in the graph and with "cylc set".
    * Messages map onto triggers and are used with "cylc message", they can
      provide additional context to an output which will appear in the workflow
      log.

    [scheduling]
        [[graph]]
            R1 = t1:trigger1 => t2
    [runtime]
        [[t1]]
            [[[outputs]]]
                trigger1 = message 1

    Args:
        tdef:
            The task definition for the task these outputs represent.

            For use outside of the scheduler, this argument can be completion
            expression string.

    """
    __slots__ = (
        "_message_to_trigger",
        "_message_to_compvar",
        "_completed",
        "_completion_expression",
        "_forced",
    )

    _message_to_trigger: Dict[str, str]  # message: trigger
    _message_to_compvar: Dict[str, str]  # message: completion variable
    _completed: Dict[str, bool]  # message: is_complete
    _completion_expression: str
    _forced: List[str]  # list of messages of force-completed outputs

    def __init__(self, tdef: 'Union[TaskDef, str]'):
        self._message_to_trigger = {}
        self._message_to_compvar = {}
        self._completed = {}
        self._forced = []

        if isinstance(tdef, str):
            # abnormal use e.g. from the "cylc show" command
            self._completion_expression = tdef
        else:
            # normal use e.g. from within the scheduler
            self._completion_expression = get_completion_expression(tdef)
            for trigger, (message, _required) in tdef.outputs.items():
                self.add(trigger, message)

    def add(self, trigger: str, message: str) -> None:
        """Register a new output.

        Note, normally outputs are listed automatically from the provided
        TaskDef so there is no need to call this interface. It exists for cases
        where TaskOutputs are used outside of the scheduler where there is no
        TaskDef object handy so outputs must be listed manually.
        """
        self._message_to_trigger[message] = trigger
        self._message_to_compvar[message] = trigger_to_completion_variable(
            trigger
        )
        self._completed[message] = False

    def get_trigger(self, message: str) -> str:
        """Return the trigger associated with this message."""
        return self._message_to_trigger[message]

    def set_trigger_complete(
        self, trigger: str, forced=False
    ) -> Optional[bool]:
        """Set the provided output trigger as complete.

        Args:
            trigger:
                The task output trigger to satisfy.

        Returns:
            True:
                If the output was unset before.
            False:
                If the output was already set.
            None
                If the output does not apply.

        """
        trg_to_msg = {
            v: k for k, v in self._message_to_trigger.items()
        }
        return self.set_message_complete(trg_to_msg[trigger], forced)

    def set_message_complete(
        self, message: str, forced=False
    ) -> Optional[bool]:
        """Set the provided task message as complete.

        Args:
            message:
                The task output message to satisfy.

        Returns:
            True:
                If the output was unset before.
            False:
                If the output was already set.
            None
                If the output does not apply.

        """
        if message not in self._completed:
            # no matching output
            return None

        if self._completed[message] is False:
            # output was incomplete
            self._completed[message] = True
            if forced:
                self._forced.append(message)
            return True

        # output was already completed
        return False

    def is_message_complete(self, message: str) -> Optional[bool]:
        """Return True if this message is complete.

        Returns:
            * True if the message is complete.
            * False if the message is not complete.
            * None if the message does not apply to these outputs.
        """
        if message in self._completed:
            return self._completed[message]
        return None

    def get_completed_outputs(self) -> Dict[str, str]:
        """Return a dict {trigger: message} of completed outputs.

        Replace message with "forced" if the output was forced.

        """
        return {
            self._message_to_trigger[message]: (
                FORCED_COMPLETION_MSG if message in self._forced else message
            )
            for message, is_completed in self._completed.items()
            if is_completed
        }

    def __iter__(self) -> Iterator[Tuple[str, str, bool]]:
        """A generator that yields all outputs.

        Yields:
            (trigger, message, is_complete)

            trigger:
                The output trigger.
            message:
                The output message.
            is_complete:
                True if the output is complete, else False.

        """
        for message, is_complete in self._completed.items():
            yield self._message_to_trigger[message], message, is_complete

    def is_complete(self) -> bool:
        """Return True if the outputs are complete."""
        # NOTE: If a task has been removed from the workflow via restart /
        # reload, then it is possible for the completion expression to be blank
        # (empty string). In this case, we consider the task outputs to be
        # complete when any final output has been generated.
        # See https://github.com/cylc/cylc-flow/pull/5067
        expr = self._completion_expression or FINAL_OUTPUT_COMPLETION
        return CompletionEvaluator(
            expr,
            **{
                self._message_to_compvar[message]: completed
                for message, completed in self._completed.items()
            },
        )

    def get_incomplete_implied(self, message: str) -> List[str]:
        """Return an ordered list of incomplete implied messages.

        Use to determined implied outputs to complete automatically.

        Implied outputs are necessarily earlier outputs.

        - started implies submitted
        - succeeded and failed imply started
        - custom outputs and expired do not imply other outputs

        """
        implied: List[str] = []

        if message in [TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED]:
            # Finished, so it must have submitted and started.
            implied = [TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED]
        elif message == TASK_OUTPUT_STARTED:
            # It must have submitted.
            implied = [TASK_OUTPUT_SUBMITTED]

        return [
            message
            for message in implied
            if not self.is_message_complete(message)
        ]

    def format_completion_status(
        self,
        indent: int = 2,
        gutter: int = 2,
        ansimarkup: int = 0,
    ) -> str:
        """Return a text representation of the status of these outputs.

        Returns a multiline string representing the status of each output used
        in the expression within the context of the expression itself.

        Args:
            indent:
                Number of spaces to indent each level of the expression.
            gutter:
                Number of spaces to pad the left column from the expression.
            ansimarkup:
                Turns on colour coding using ansimarkup tags. These will need
                to be parsed before display. There are three options

                0:
                    No colour coding.
                1:
                    Only success colours will be used. This is easier to read
                    in colour coded logs.
                2:
                    Both success and fail colours will be used.

        Returns:
            A multiline textural representation of the completion status.

        """
        indent_space: str = ' ' * indent
        _gutter: str = ' ' * gutter

        def color_wrap(string, is_complete):
            nonlocal ansimarkup
            if ansimarkup == 0:
                return string
            if is_complete:
                return f'<green>{string}</green>'
            if ansimarkup == 2:
                return f'<red>{string}</red>'
            return string

        ret: List[str] = []
        indent_level: int = 0
        op: Optional[str] = None
        fence = '┆'  # U+2506 (Box Drawings Light Triple Dash Vertical)
        for part in RE_EXPR_SPLIT.split(self._completion_expression):
            if not part.strip():
                continue

            if part in {'and', 'or'}:
                op = part
                continue

            elif part == '(':
                if op:
                    ret.append(
                        f'  {fence}{_gutter}{(indent_space * indent_level)}'
                        f'{op} {part}'
                    )
                else:
                    ret.append(
                        f'  {fence}{_gutter}'
                        f'{(indent_space * indent_level)}{part}'
                    )
                indent_level += 1
            elif part == ')':
                indent_level -= 1
                ret.append(
                    f'  {fence}{_gutter}{(indent_space * indent_level)}{part}'
                )

            else:
                _symbol = BOOL_SYMBOLS[bool(self._is_compvar_complete(part))]
                is_complete = self._is_compvar_complete(part)
                _pre = (
                    f'{color_wrap(_symbol, is_complete)} {fence}'
                    f'{_gutter}{(indent_space * indent_level)}'
                )
                if op:
                    ret.append(f'{_pre}{op} {color_wrap(part, is_complete)}')
                else:
                    ret.append(f'{_pre}{color_wrap(part, is_complete)}')

            op = None

        return '\n'.join(ret)

    @staticmethod
    def is_valid_std_name(name: str) -> bool:
        """Check name is a valid standard output name."""
        return name in TASK_OUTPUTS

    @staticmethod
    def output_sort_key(item: Iterable[str]) -> float:
        """Compare by output order.

        Examples:
            >>> this = TaskOutputs.output_sort_key
            >>> sorted(['finished', 'started',  'custom'], key=this)
            ['started', 'custom', 'finished']

        """
        if item in TASK_OUTPUTS:
            return TASK_OUTPUTS.index(item)
        # Sort custom outputs after started.
        return TASK_OUTPUTS.index(TASK_OUTPUT_STARTED) + .5

    def _is_compvar_complete(self, compvar: str) -> Optional[bool]:
        """Return True if the completion variable is complete.

        Returns:
            * True if var is optional.
            * False if var is required.
            * None if var is not referenced.

        """
        for message, _compvar in self._message_to_compvar.items():
            if _compvar == compvar:
                return self.is_message_complete(message)
        else:
            raise KeyError(compvar)

    def iter_required_messages(
        self,
        disable: 'Optional[Literal["succeeded", "failed"]]' = None
    ) -> Iterator[str]:
        """Yield task messages that are required for this task to be complete.

        Note, in some cases tasks might not have any required messages,
        e.g. "completion = succeeded or failed".

        Args:
            disable: Consider this output and any others it is joined with by
                `and` to not exist. In skip mode we only want to check either
                succeeded or failed, but not both.
        """
        for compvar, is_optional in get_optional_outputs(
            self._completion_expression,
            set(self._message_to_compvar.values()),
            disable=disable
        ).items():
            if is_optional is False:
                for message, _compvar in self._message_to_compvar.items():
                    if _compvar == compvar:
                        yield message

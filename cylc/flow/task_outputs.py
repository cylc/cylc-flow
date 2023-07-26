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

from cylc.flow.exceptions import InvalidCompletionExpression
from cylc.flow.util import restricted_evaluator


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
    TASK_OUTPUT_FAILED)

TASK_OUTPUTS = (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_FINISHED,
)

_TRIGGER = 0
_MESSAGE = 1
_IS_COMPLETED = 2


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


def trigger_to_completion_variable(output):
    """Turn a trigger into something that can be used in an expression.

    Examples:
        >>> trigger_to_completion_variable('succeeded')
        'succeeded'
        >>> trigger_to_completion_variable('submit-failed')
        'submit_failed'

    """
    return output.replace('-', '_')


def get_completion_expression(tdef):
    """Return a task's completion expression."""
    expr = tdef.rtconfig.get('completion')
    if expr:
        # the expression has been explicitly provided in the configuration
        return expr

    # default behaviour:
    # * succeeded is a required output unless stated otherwise
    # * if optional outputs are defined in the graph, one or more must be
    #   generated.
    ands = []
    ors = []
    for trigger, (_message, required) in tdef.outputs.items():
        trig = trigger_to_completion_variable(trigger)
        if required is True:
            ands.append(trig)
        if required is False:
            ors.append(trig)

    if not ands and not ors:
        # task is not used in the graph
        # e.g. task has been removed by restart/reload
        # we cannot tell what the completion condition was because it is not
        # defined in the runtime section so we allow any completion status
        return 'succeeded or failed or expired'

    # sort for stable output
    ands.sort()
    ors.sort()

    # join the lists of "ands" and "ors" into statements
    _ands = ''
    if ands:
        _ands = ' and '.join(ands)
    _ors = ''
    if ors:
        _ors = ' or '.join(ors)

    # join the statements of "ands" and "ors" into an expression
    if ands and ors:
        if len(ors) > 1:
            expr = f'{_ands} and ({_ors})'
        else:
            expr = f'{_ands} and {_ors}'
    elif ands:
        expr = _ands
    else:
        expr = _ors

    return expr


def get_optional_outputs(expression, outputs):
    """Determine which outputs are optional in an expression

    Raises:
        NameError:
            If an output referenced in the expression is not present in the
            outputs dict provided.
        InvalidCompletionExpression:
            If any syntax used in the completion expression is not permitted.
        Exception:
            For errors executing the completion expression itself.

    """
    _outputs = [trigger_to_completion_variable(o) for o in outputs]
    return {  # output: is_optional
        output: CompletionEvaluator(
            expression,
            **{o: o != output for o in _outputs}
        )
        for output in _outputs
    }


def get_used_outputs(expression, outputs):
    """Return all outputs which are used in the expression.

    Called on stall to determine what outputs weren't generated.
    """
    return {
        output
        for output in outputs
        if re.findall(rf'\b{output}\b', expression)
    }


class TaskOutputs:
    """Task output message manager.

    Manage standard task outputs and custom outputs, e.g.:
    [scheduling]
        [[graph]]
            R1 = t1:trigger1 => t2
    [runtime]
        [[t1]]
            [[[outputs]]]
                trigger1 = message 1

    Can search item by message string or by trigger string.
    """

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["_by_message", "_by_trigger", "_completion_expression"]

    def __init__(self, tdef):
        self._by_message = {}
        self._by_trigger = {}
        self._completion_expression = get_completion_expression(tdef)
        # Add outputs from task def.
        for trigger, (message, _required) in tdef.outputs.items():
            self._add(message, trigger)

    def _add(self, message, trigger, is_completed=False):
        """Add a new output message"""
        self._by_message[message] = [trigger, message, is_completed]
        self._by_trigger[trigger] = self._by_message[message]

    def set_completed_by_msg(self, message):
        """For flow trigger --wait: set completed outputs from the DB."""
        for trig, msg, _ in self._by_trigger.values():
            if message == msg:
                self._add(message, trig, True)
                break

    def all_completed(self):
        """Return True if all all outputs completed."""
        return all(val[_IS_COMPLETED] for val in self._by_message.values())

    def exists(self, message=None, trigger=None):
        """Return True if message/trigger is identified as an output."""
        try:
            return self._get_item(message, trigger) is not None
        except KeyError:
            return False

    def get_all(self):
        """Return an iterator for all outputs."""
        return sorted(self._by_message.values(), key=self.msg_sort_key)

    def get_completed(self):
        """Return all completed output messages."""
        ret = []
        for value in self.get_all():
            if value[_IS_COMPLETED]:
                ret.append(value[_MESSAGE])
        return ret

    def get_completed_all(self):
        """Return all completed outputs.

        Return a list in this form: [(trigger1, message1), ...]
        """
        ret = []
        for value in self.get_all():
            if value[_IS_COMPLETED]:
                ret.append((value[_TRIGGER], value[_MESSAGE]))
        return ret

    def has_custom_triggers(self):
        """Return True if it has any custom triggers."""
        return any(key not in SORT_ORDERS for key in self._by_trigger)

    def get_not_completed(self):
        """Return all not-completed output messages."""
        ret = []
        for value in self.get_all():
            if not value[_IS_COMPLETED]:
                ret.append(value[_MESSAGE])
        return ret

    def is_completed(self, message=None, trigger=None):
        """Return True if output of message is completed."""
        try:
            return self._get_item(message, trigger)[_IS_COMPLETED]
        except KeyError:
            return False

    def remove(self, message=None, trigger=None):
        """Remove an output by message, if it exists."""
        try:
            trigger, message = self._get_item(message, trigger)[:2]
        except KeyError:
            pass
        else:
            del self._by_message[message]
            del self._by_trigger[trigger]

    def set_all_completed(self):
        """Set all outputs to complete."""
        for value in self._by_message.values():
            value[_IS_COMPLETED] = True

    def set_all_incomplete(self):
        """Set all outputs to incomplete."""
        for value in self._by_message.values():
            value[_IS_COMPLETED] = False

    def set_completion(self, message, is_completed):
        """Set output message completion status to is_completed (bool)."""
        if message in self._by_message:
            self._by_message[message][_IS_COMPLETED] = is_completed

    def set_msg_trg_completion(self, message=None, trigger=None,
                               is_completed=True):
        """Set the output identified by message/trigger to is_completed.

        Return:
            - Value of trigger (True) if completion flag is changed,
            - False if completion is unchanged, or
            - None if message/trigger is not found.

        """
        try:
            item = self._get_item(message, trigger)
            old_is_completed = item[_IS_COMPLETED]
            item[_IS_COMPLETED] = is_completed
        except KeyError:
            return None
        else:
            if bool(old_is_completed) == bool(is_completed):
                return False
            else:
                return item[_TRIGGER]

    def is_incomplete(self):
        """Return True if any required outputs are not complete."""
        outputs = {
            trigger_to_completion_variable(trigger): completed
            for trigger, (_, _, completed) in self._by_trigger.items()
        }
        return not CompletionEvaluator(self._completion_expression, **outputs)

    def get_incomplete(self):
        """Return a list of outputs that are not complete."""
        used_outputs = get_used_outputs(
            self._completion_expression,
            self._by_trigger,
        )
        return sorted(
            trigger
            for trigger, (_, _, is_completed) in self._by_trigger.items()
            if not is_completed
            and trigger in used_outputs
        )

    def get_item(self, message):
        """Return output item by message.

        Args:
            message (str): Output message.

        Returns:
            item (tuple):
                label (str), message (str), satisfied (bool)

        """
        if message in self._by_message:
            return self._by_message[message]

    def _get_item(self, message, trigger):
        """Return self._by_trigger[trigger] or self._by_message[message].

        whichever is relevant.
        """
        if message is None:
            return self._by_trigger[trigger]
        else:
            return self._by_message[message]

    @staticmethod
    def is_valid_std_name(name):
        """Check name is a valid standard output name."""
        return name in SORT_ORDERS

    @staticmethod
    def msg_sort_key(item):
        """Compare by _MESSAGE."""
        try:
            ind = SORT_ORDERS.index(item[_MESSAGE])
        except ValueError:
            ind = 999
        return (ind, item[_MESSAGE] or '')

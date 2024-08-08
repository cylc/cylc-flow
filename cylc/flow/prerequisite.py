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

"""Functionality for expressing and evaluating logical triggers."""

import math
import re
from typing import (
    TYPE_CHECKING,
    Dict,
    ItemsView,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Union,
)

# BACK COMPAT: typing_extensions.Literal
# FROM: Python 3.7
# TO: Python 3.8
from typing_extensions import Literal

from cylc.flow.cycling.loader import get_point
from cylc.flow.data_messages_pb2 import PbCondition, PbPrerequisite
from cylc.flow.exceptions import TriggerExpressionError
from cylc.flow.id import quick_relative_detokenise


if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase
    from cylc.flow.id import Tokens


AnyPrereqMessage = Tuple[Union['PointBase', str, int], str, str]


class PrereqMessage(NamedTuple):
    """A message pertaining to a Prerequisite."""
    point: str
    task: str
    output: str

    def get_id(self) -> str:
        """Get the relative ID of the task in this prereq message."""
        return quick_relative_detokenise(self.point, self.task)

    @staticmethod
    def coerce(tuple_: AnyPrereqMessage) -> 'PrereqMessage':
        """Coerce a tuple to a PrereqMessage."""
        if isinstance(tuple_, PrereqMessage):
            return tuple_
        point, task, output = tuple_
        return PrereqMessage(point=str(point), task=task, output=output)


SatisfiedState = Literal[
    'satisfied naturally',
    'satisfied from database',
    'force satisfied',
    False
]


class Prerequisite:
    """The concrete result of an abstract logical trigger expression.

    A single TaskProxy can have multiple Prerequisites, all of which require
    satisfying. This corresponds to multiple tasks being dependencies of a task
    in Cylc graphs (e.g. `a => c`, `b => c`). But a single Prerequisite can
    also have multiple 'messages' (basically, subcomponents of a Prerequisite)
    corresponding to parenthesised expressions in Cylc graphs (e.g.
    `(a & b) => c` or `(a | b) => c`). For the OR operator (`|`), only one
    message has to be satisfied for the Prerequisite to be satisfied.
    """

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = (
        "_satisfied",
        "_all_satisfied",
        "conditional_expression",
        "point",
    )

    # Extracts T from "foo.T succeeded" etc.
    SATISFIED_TEMPLATE = 'bool(self._satisfied[("%s", "%s", "%s")])'
    MESSAGE_TEMPLATE = r'%s/%s %s'

    def __init__(self, point: 'PointBase'):
        # The cycle point to which this prerequisite belongs.
        # cylc.flow.cycling.PointBase
        self.point = point

        # Dictionary of messages pertaining to this prerequisite.
        # {('point string', 'task name', 'output'): DEP_STATE_X, ...}
        self._satisfied: Dict[PrereqMessage, SatisfiedState] = {}

        # Expression present only when conditions are used.
        # '1/foo failed & 1/bar succeeded'
        self.conditional_expression: Optional[str] = None

        # The cached state of this prerequisite:
        # * `None` (no cached state)
        # * `True` (prerequisite satisfied)
        # * `False` (prerequisite unsatisfied).
        self._all_satisfied: Optional[bool] = None

    def instantaneous_hash(self) -> int:
        """Generate a hash of this prerequisite in its current state.

        NOTE: Is not affected by any change in satisfaction state.

        (Not defining `self.__hash__()` because Prerequisite objects
        are mutable.)
        """
        return hash((
            self.point,
            self.conditional_expression,
            tuple(self._satisfied.keys()),
        ))

    def __getitem__(self, key: AnyPrereqMessage) -> SatisfiedState:
        """Return the satisfaction state of a dependency.

        Args:
            key: Tuple of (point, name, output) for a task.
        """
        return self._satisfied[PrereqMessage.coerce(key)]

    def __setitem__(
        self,
        key: AnyPrereqMessage,
        value: Union[SatisfiedState, bool] = False,
    ) -> None:
        """Register an output with this prerequisite.

        Args:
            key: Tuple of (point, name, output) for a prerequisite task.
            value: Dependency satisfaction state (for pre-initial dependencies
                this should be True).

        """
        key = PrereqMessage.coerce(key)
        if value is True:
            value = 'satisfied naturally'
        self._satisfied[key] = value
        if not (self._all_satisfied and value):
            # Force later recalculation of cached satisfaction state:
            self._all_satisfied = None

    def __iter__(self) -> Iterator[PrereqMessage]:
        return iter(self._satisfied)

    def items(self) -> ItemsView[PrereqMessage, SatisfiedState]:
        return self._satisfied.items()

    def get_raw_conditional_expression(self):
        """Return a representation of this prereq as a string.

        Returns None if this prerequisite is not a conditional one.

        """
        expr = self.conditional_expression
        if not expr:
            return None
        for message in self._satisfied:
            expr = expr.replace(self.SATISFIED_TEMPLATE % message,
                                self.MESSAGE_TEMPLATE % message)
        return expr

    def set_condition(self, expr):
        """Set the conditional expression for this prerequisite.
        Resets the cached state (self._all_satisfied).

        Examples:
            # GH #3644 construct conditional expression when one task name
            # is a substring of another: foo | xfoo => bar.
            # Add 'foo' to the 'satisfied' dict before 'xfoo'.
            >>> preq = Prerequisite(1)
            >>> preq[(1, 'foo', 'succeeded')] = False
            >>> preq[(1, 'xfoo', 'succeeded')] = False
            >>> preq.set_condition("1/foo succeeded|1/xfoo succeeded")
            >>> expr = preq.conditional_expression
            >>> expr.split('|')  # doctest: +NORMALIZE_WHITESPACE
            ['bool(self._satisfied[("1", "foo", "succeeded")])',
            'bool(self._satisfied[("1", "xfoo", "succeeded")])']

        """
        self._all_satisfied = None
        if '|' in expr:
            # Make a Python expression so we can eval() the logic.
            for message in self._satisfied:
                # Use '\b' in case one task name is a substring of another
                # and escape special chars ('.', timezone '+') in task IDs.
                expr = re.sub(
                    fr"\b{re.escape(self.MESSAGE_TEMPLATE % message)}\b",
                    self.SATISFIED_TEMPLATE % message,
                    expr
                )

            self.conditional_expression = expr

    def is_satisfied(self):
        """Return True if prerequisite is satisfied.

        Return cached state if present, else evaluate the prerequisite.

        """
        if self._all_satisfied is not None:
            # Cached value.
            return self._all_satisfied
        if self._satisfied == {}:
            # No prerequisites left after pre-initial simplification.
            return True
        self._all_satisfied = self._eval_satisfied()
        return self._all_satisfied

    def _eval_satisfied(self) -> bool:
        """Evaluate the prerequisite's condition expression.

        Does not cache the result.

        """
        if not self.conditional_expression:
            return all(self._satisfied.values())

        try:
            res = eval(self.conditional_expression)  # nosec
            # * the expression is constructed internally
            # * https://github.com/cylc/cylc-flow/issues/4403
        except (SyntaxError, ValueError) as exc:
            err_msg = str(exc)
            if str(exc).find("unexpected EOF") != -1:
                err_msg += (
                    " (could be unmatched parentheses in the graph string?)")
            raise TriggerExpressionError(
                '"%s":\n%s' % (self.get_raw_conditional_expression(), err_msg)
            ) from None
        return res

    def satisfy_me(self, outputs: Iterable['Tokens']) -> 'Set[Tokens]':
        """Attempt to satisfy me with given outputs.

        Updates cache with the result.
        Return outputs that match.

        """
        valid = set()
        for output in outputs:
            prereq = PrereqMessage(
                output['cycle'], output['task'], output['task_sel']
            )
            if prereq not in self._satisfied:
                continue
            valid.add(output)
            self[prereq] = 'satisfied naturally'
        return valid

    def api_dump(self) -> Optional[PbPrerequisite]:
        """Return list of populated Protobuf data objects."""
        if not self._satisfied:
            return None
        if self.conditional_expression:
            expr = (
                self.get_raw_conditional_expression()
            ).replace('|', ' | ').replace('&', ' & ')
        else:
            expr = ' & '.join(
                self.MESSAGE_TEMPLATE % s_msg
                for s_msg in self._satisfied
            )
        conds = []
        num_length = math.ceil(len(self._satisfied) / 10)
        for ind, message_tuple in enumerate(sorted(self._satisfied)):
            t_id = message_tuple.get_id()
            char = 'c%.{0}d'.format(num_length) % ind
            c_msg = self.MESSAGE_TEMPLATE % message_tuple
            c_val = self._satisfied[message_tuple]
            conds.append(
                PbCondition(
                    task_proxy=t_id,
                    expr_alias=char,
                    req_state=message_tuple.output,
                    satisfied=bool(c_val),
                    message=(c_val or 'unsatisfied'),
                )
            )
            expr = expr.replace(c_msg, char)
        return PbPrerequisite(
            expression=expr,
            satisfied=self.is_satisfied(),
            conditions=conds,
            cycle_points=sorted(self.iter_target_point_strings()),
        )

    def set_satisfied(self) -> None:
        """Force this prerequisite into the satisfied state.

        State can be overridden by calling `self.satisfy_me`.

        """
        for message in self._satisfied:
            if not self._satisfied[message]:
                self._satisfied[message] = 'force satisfied'
        if self.conditional_expression:
            self._all_satisfied = self._eval_satisfied()
        else:
            self._all_satisfied = True

    def iter_target_point_strings(self):
        yield from {
            message.point for message in self._satisfied
        }

    def get_target_points(self):
        """Return a list of cycle points target by each prerequisite,
        including each component of conditionals."""
        return [
            get_point(p) for p in self.iter_target_point_strings()
        ]

    def get_resolved_dependencies(self) -> List[str]:
        """Return a list of satisfied dependencies.

        E.G: ['1/foo', '2/bar']

        """
        return [
            msg.get_id()
            for msg, satisfied in self._satisfied.items()
            if satisfied
        ]

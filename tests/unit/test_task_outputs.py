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

import random
from types import SimpleNamespace

import pytest

from cylc.flow.taskdef import (
    set_implicit_required_outputs,
)
from cylc.flow.task_outputs import (
    TASK_OUTPUTS,
    CompletionEvaluator,
    TaskOutputs,
    get_completion_expression,
    get_used_outputs,
)


TEST_MESSAGES = [
    ['expired', 'expired', False],
    ['submitted', 'submitted', False],
    ['submit-failed', 'submit-failed', False],
    ['started', 'started', False],
    ['succeeded', 'succeeded', False],
    ['failed', 'failed', False],
    [None, None, False],
    ['foo', 'bar', False],
    ['foot', 'bart', False],
    # NOTE: [None, 'bar', False] is unstable under Python2
]


def test_sorting():
    messages = list(TEST_MESSAGES)
    for _ in range(5):
        random.shuffle(messages)
        output = sorted(messages, key=TaskOutputs.msg_sort_key)
        assert output == TEST_MESSAGES


def make_tdef(
    opt_outputs=None,
    req_outputs=None,
    completion=None,
    set_implicit=True,
):
    """Return a TaskDef-like object for completion expression purposes.

    Args:
        opt_outputs: List of optional outputs or None.
        req_outputs: List of required outputs or None.
        completion: Custom completion expression or None.
        set_implicit: Set implicit outputs (not done for removed tasks).

    Returns:
        Something with enough information to pass as a TaskDef.

    """
    opt_outputs = opt_outputs or []
    req_outputs = req_outputs or []
    tdef = SimpleNamespace(
        rtconfig={
            'completion': completion,
        },
        outputs={
            **{output: (output, None) for output in TASK_OUTPUTS},
            **{output: (output, False) for output in opt_outputs},
            **{output: (output, True) for output in req_outputs},
        },
    )
    if set_implicit:
        set_implicit_required_outputs(tdef.outputs)
    return tdef


@pytest.mark.parametrize(
    'opt_outputs, req_outputs, completion, expression',
    [
        pytest.param(
            None,
            None,
            None,
            'succeeded',
            id='default',
        ),
        pytest.param(
            ['x'],
            None,
            None,
            'succeeded and x',
            id='single-optional-output'
        ),
        pytest.param(
            ['x', 'y', 'z'],
            None,
            None,
            'succeeded and (x or y or z)',
            id='multiple-optional-outputs'
        ),
        pytest.param(
            None,
            ['succeeded', 'x', 'y', 'z'],
            None,
            'succeeded and x and y and z',
            id='multiple-required-outputs'
        ),
        pytest.param(
            ['succeeded', 'failed', 'expired'],
            None,
            None,
            'expired or failed or succeeded',
            id='multiple-optional-outputs-no-required-outputs'
        ),
        pytest.param(
            ['a', 'b', 'c'],
            ['succeeded', 'x', 'y', 'z'],
            None,
            'succeeded and x and y and z and (a or b or c)',
            id='multiple-optional-and-required-outputs'
        ),
        pytest.param(
            None,
            None,
            '(succeeded and x) or (failed and y)',
            '(succeeded and x) or (failed and y)',
            id='custom-completion-expression'
        ),
    ]
)
def test_completion_expression(
    opt_outputs,
    req_outputs,
    completion,
    expression
):
    """It should derive a completion expression where not explicitly stated.

    See proposal point (2) for spec:
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-optional-output-extension.md#proposal
    """
    expr = get_completion_expression(
        make_tdef(opt_outputs, req_outputs, completion)
    )
    assert expr == expression


def test_completed_expression_removed_task():
    """It should handle tasks not present in the graph.

    If an active task is removed by restart/reload, then we may be left with a
    task which does not exist in the graph and might not even have a
    definition in the config.

    In these cases we should allow any final outcome.
    """
    assert get_completion_expression(make_tdef(set_implicit=False)) == (
        'succeeded or failed or expired'
    )


@pytest.mark.parametrize(
    'expression, outputs, outcome',
    [
        (
            'succeeded',
            {'succeeded': False},
            False,
        ),
        (
            'succeeded',
            {'succeeded': True},
            True,
        ),
        (
            '(succeeded and x) or (failed and y)',
            {'succeeded': True, 'x': True, 'failed': False, 'y': False},
            True,
        ),
    ]
)
def test_completion_evaluator(expression, outputs, outcome):
    """It should evaluate completion expressions against output states."""
    assert CompletionEvaluator(expression, **outputs) == outcome


def test_output_is_incomplete():
    """It should report when outputs are complete.

    And which ouputs are incomplete.
    """
    tdef = make_tdef(
        opt_outputs=['x', 'y', 'z'],
        req_outputs=['succeeded', 'a'],
    )
    outputs = TaskOutputs(tdef)

    # the outputs should be incomplete on initialisation
    assert outputs.is_incomplete()

    # only the referenced outputs should be returned as incomplete
    # (i.e. submitted, started, expired, etc should be filtered out)
    assert outputs.get_incomplete() == ['a', 'succeeded', 'x', 'y', 'z']

    # set 'a' and 'succeeded' as completed
    outputs.set_completion('a', True)
    outputs.set_completion('succeeded', True)

    # the outputs should still be incomplete
    assert outputs.is_incomplete()
    assert outputs.get_incomplete() == ['x', 'y', 'z']

    # set the 'x' output as completed
    outputs.set_completion('x', True)

    # the outputs should now be complete
    assert not outputs.is_incomplete()
    assert outputs.get_incomplete() == ['y', 'z']


@pytest.mark.parametrize(
    'expression, outputs, used',
    [
        # the 'y' output is not used
        pytest.param(
            'succeeded and x',
            {'succeeded', 'x', 'y'},
            {'succeeded', 'x'},
            id='1',
        ),
        # the 'x' output is not used
        # (but some used outputs begin with the letter 'x')
        pytest.param(
            'xy or xz',
            {'x', 'xy', 'xz'},
            {'xy', 'xz'},
            id='2',
        ),
        pytest.param(
            'a or (b and c) or (d and (e or f))',
            {'a', 'b', 'c', 'd', 'e', 'f'},
            {'a', 'b', 'c', 'd', 'e', 'f'},
            id='3',
        ),
    ]
)
def test_get_used_outputs(expression, outputs, used):
    """It should return outputs referenced in the completion expression."""
    assert get_used_outputs(
        expression,
        ['submitted', 'started', *outputs],
    ) == used

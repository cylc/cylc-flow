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

from types import SimpleNamespace

import pytest

from cylc.flow.task_outputs import (
    TASK_OUTPUTS,
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_SUCCEEDED,
    TaskOutputs,
    get_completion_expression,
    get_trigger_completion_variable_maps,
)
from cylc.flow.util import sstrip


def tdef(required, optional, completion=None):
    """Stub a task definition.

    Args:
        required: Collection of required outputs.
        optional: Collection of optional outputs.
        completion: User defined execution completion expression.

    """
    return SimpleNamespace(
        rtconfig={
            'completion': completion,
        },
        outputs={
            output: (
                output,
                (
                    # output is required:
                    True if output in required
                    # output is optional:
                    else False if output in optional
                    # output is ambiguous (i.e. not referenced in graph):
                    else None
                )
            )
            for output in set(TASK_OUTPUTS) | set(required) | set(optional)
        },
    )


def test_completion_implicit():
    """It should generate a completion expression when none is provided.

    The outputs should be considered "complete" according to the logic in
    proposal point 5:
    https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal
    """
    # one required output - succeeded
    outputs = TaskOutputs(tdef([TASK_OUTPUT_SUCCEEDED], []))

    # the completion expression should only contain the one required output
    assert outputs._completion_expression == 'succeeded'
    # the outputs should be incomplete - it hasn't run yet
    assert outputs.is_complete() is False

    # set the submit-failed output
    outputs.set_message_complete(TASK_OUTPUT_SUBMIT_FAILED)
    # the outputs should be incomplete - submited-failed is a "final" output
    assert outputs.is_complete() is False

    # set the submitted and succeeded outputs
    outputs.set_message_complete(TASK_OUTPUT_SUBMITTED)
    outputs.set_message_complete(TASK_OUTPUT_SUCCEEDED)
    # the outputs should be complete - it has run an succeedd
    assert outputs.is_complete() is True

    # set the expired output
    outputs.set_message_complete(TASK_OUTPUT_EXPIRED)
    # the outputs should still be complete - it has run and succeeded
    assert outputs.is_complete() is True


def test_completion_explicit():
    """It should use the provided completion expression.

    The outputs should be considered "complete" according to the logic in
    proposal point 5:
    https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal
    """
    outputs = TaskOutputs(tdef(
        # no required outputs
        [],
        # four optional outputs
        [
            TASK_OUTPUT_SUCCEEDED,
            TASK_OUTPUT_FAILED,
            'x',
            'y',
        ],
        # one pair must be satisfied for the outputs to be complete
        completion='(succeeded and x) or (failed and y)',
    ))

    # the outputs should be incomplete - it hasn't run yet
    assert outputs.is_complete() is False

    # set the succeeded and failed outputs
    outputs.set_message_complete(TASK_OUTPUT_SUCCEEDED)
    outputs.set_message_complete(TASK_OUTPUT_FAILED)

    # the task should be incomplete - it has executed but the completion
    # expression is not satisfied
    assert outputs.is_complete() is False

    # satisfy the (failed and y) pair
    outputs.set_message_complete('y')
    assert outputs.is_complete() is True

    # satisfy the (succeeded and x) pair
    outputs._completed['y'] = False
    outputs.set_message_complete('x')
    assert outputs.is_complete() is True


@pytest.mark.parametrize(
    'required, optional, expression', [
        pytest.param(
            {TASK_OUTPUT_SUCCEEDED},
            [],
            'succeeded',
            id='0',
        ),
        pytest.param(
            {TASK_OUTPUT_SUCCEEDED, 'x'},
            [],
            '(succeeded and x)',
            id='1',
        ),
        pytest.param(
            [],
            {TASK_OUTPUT_SUCCEEDED},
            'succeeded or failed',
            id='2',
        ),
        pytest.param(
            {TASK_OUTPUT_SUCCEEDED},
            {TASK_OUTPUT_EXPIRED},
            'succeeded or expired',
            id='3',
        ),
        pytest.param(
            [],
            {TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_EXPIRED},
            'succeeded or failed or expired',
            id='4',
        ),
        pytest.param(
            {TASK_OUTPUT_SUCCEEDED},
            {TASK_OUTPUT_EXPIRED, TASK_OUTPUT_SUBMITTED},
            'succeeded or submit_failed or expired',
            id='5',
        ),
        pytest.param(
            {TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_SUBMITTED},
            {TASK_OUTPUT_EXPIRED},
            '(submitted and succeeded) or expired',
            id='6',
        ),
        pytest.param(
            [],
            {TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_SUBMIT_FAILED},
            'succeeded or failed or submit_failed',
            id='7',
        ),
        pytest.param(
            {'x'},
            {
                TASK_OUTPUT_SUCCEEDED,
                TASK_OUTPUT_SUBMIT_FAILED,
                TASK_OUTPUT_EXPIRED,
            },
            '(x and succeeded) or failed or submit_failed or expired',
            id='8',
        ),
    ],
)
def test_get_completion_expression_implicit(required, optional, expression):
    """It should generate a completion expression if none is provided."""
    assert get_completion_expression(tdef(required, optional)) == expression


def test_get_completion_expression_explicit():
    """If a completion expression is used, it should be used unmodified."""
    assert get_completion_expression(tdef(
        {'x', 'y'},
        {TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED, TASK_OUTPUT_EXPIRED},
        '((failed and x) or (succeeded and y)) or expired'
    )) == '((failed and x) or (succeeded and y)) or expired'


def test_format_completion_status():
    outputs = TaskOutputs(
        tdef(
            {TASK_OUTPUT_SUCCEEDED, 'x', 'y'},
            {TASK_OUTPUT_EXPIRED},
        )
    )
    assert outputs.format_completion_status(
        indent=2, gutter=2
    ) == '  ' + sstrip(
        '''
          ┆  (
        ⨯ ┆    succeeded
        ⨯ ┆    and x
        ⨯ ┆    and y
          ┆  )
        ⨯ ┆  or expired
        '''
    )
    outputs.set_message_complete('succeeded')
    outputs.set_message_complete('x')
    assert outputs.format_completion_status(
        indent=2, gutter=2
    ) == '  ' + sstrip(
        '''
          ┆  (
        ✓ ┆    succeeded
        ✓ ┆    and x
        ⨯ ┆    and y
          ┆  )
        ⨯ ┆  or expired
        '''
    )


def test_iter_required_outputs():
    """It should yield required outputs only."""
    # this task has three required outputs and one optional output
    outputs = TaskOutputs(
        tdef(
            {TASK_OUTPUT_SUCCEEDED, 'x', 'y'},
            {'z'}
        )
    )
    assert set(outputs.iter_required_messages()) == {
        TASK_OUTPUT_SUCCEEDED,
        'x',
        'y',
    }

    # this task does not have any required outputs (besides the implicitly
    # required submitted/started outputs)
    outputs = TaskOutputs(
        tdef(
            # Note: validation should prevent this at the config level
            {TASK_OUTPUT_SUCCEEDED, 'x', 'y'},
            {TASK_OUTPUT_FAILED},  # task may fail
        )
    )
    assert set(outputs.iter_required_messages()) == set()

    # the preconditions expiry/submitted are excluded from this logic when
    # defined as optional:
    outputs = TaskOutputs(
        tdef(
            {TASK_OUTPUT_SUCCEEDED, 'x', 'y'},
            {TASK_OUTPUT_EXPIRED},  # task may expire
        )
    )
    assert (
        outputs._completion_expression == '(succeeded and x and y) or expired'
    )
    assert set(outputs.iter_required_messages()) == {
        TASK_OUTPUT_SUCCEEDED,
        'x',
        'y',
    }


def test_iter_required_outputs__disable():
    # Get all outputs required for success path (excluding failure, what
    # is still required):
    outputs = TaskOutputs(
        tdef(
            {},
            {'a', 'succeeded', 'b', 'y', 'failed', 'x'},
            '(x and y and failed) or (a and b and succeeded)'
        )
    )

    assert set(outputs.iter_required_messages()) == set()

    # Disabling succeeded leaves us with failure required outputs:
    assert set(
        outputs.iter_required_messages(disable=TASK_OUTPUT_SUCCEEDED)
    ) == {
        TASK_OUTPUT_FAILED,
        'x',
        'y',
    }

    # Disabling failed leaves us with succeeded required outputs:
    assert set(outputs.iter_required_messages(disable=TASK_OUTPUT_FAILED)) == {
        TASK_OUTPUT_SUCCEEDED,
        'a',
        'b',
    }

    # Disabling an abitrary output leaves us with required outputs
    # from another branch:
    assert set(outputs.iter_required_messages(disable='a')) == {
        TASK_OUTPUT_FAILED,
        'x',
        'y',
    }


def test_get_trigger_completion_variable_maps():
    """It should return a bi-map of triggers to compvars."""
    t2c, c2t = get_trigger_completion_variable_maps(('a', 'b-b', 'c-c-c'))
    assert t2c == {'a': 'a', 'b-b': 'b_b', 'c-c-c': 'c_c_c'}
    assert c2t == {'a': 'a', 'b_b': 'b-b', 'c_c_c': 'c-c-c'}

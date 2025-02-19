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

"""Test validation of the [runtime][<namespace>][outputs] section."""

from random import random

import pytest

from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.unicode_rules import TaskOutputValidator, TaskMessageValidator


@pytest.mark.parametrize(
    'outputs, valid',
    [
        pytest.param(
            [
                'foo',
                'foo-bar',
                'foo_bar',
                '0foo0',
                '123',
            ],
            True,
            id='valid',
        ),
        pytest.param(
            [
                # special prefix
                '_cylc',
                # nasty chars
                'foo bar',
                'foo,bar',
                'foo/bar',
                'foo+bar',
                # keywords
                'required',
                'optional',
                'all',
                # built-in qualifiers
                'succeeded',
                'succeed-all',
                # alternative qualifiers
                'succeed',
            ],
            False,
            id='invalid',
        ),
    ],
)
def test_outputs(outputs, valid, flow, validate):
    """It should validate task outputs.

    Outputs i.e. the keys of the [outputs] section.

    We don't want users adding outputs that override built-in
    outputs (e.g. succeeded, failed) or qualifiers (e.g. succeed-all).

    We don't want users adding outputs that conflict with keywords e.g.
    "required" or "all".
    """
    # test that each output validates correctly
    for output in outputs:
        assert TaskOutputValidator.validate(output)[0] is valid

    # test that output validation is actually being performed
    id_ = flow({
        'scheduling': {
            'graph': {'R1': 'foo'}
        },
        'runtime': {
            'foo': {
                'outputs': {
                    output: str(random())
                    for output in outputs
                }
            }
        },
    })
    val = lambda: validate(id_)
    if valid:
        val()
    else:
        with pytest.raises(WorkflowConfigError):
            val()


@pytest.mark.parametrize(
    'messages, valid',
    [
        pytest.param(
            [
                'foo bar baz',
                'WARN:foo bar baz'
            ],
            True,
            id='valid',
        ),
        pytest.param(
            [
                # special prefix
                '_cylc',
                # invalid colon usage
                'foo bar: baz'
                # built-in qualifiers
                'succeeded',
                'succeed-all',
                # alternative qualifiers
                'succeed',
            ],
            False,
            id='invalid',
        ),
    ],
)
def test_messages(messages, valid, flow, validate):
    """It should validate task messages.

    Messages i.e. the values of the [outputs] section.

    We don't want users adding messages that override built-in outputs (e.g.
    succeeded, failed). To avoid confusion it's best to prohibit outputs which
    override built-in qualifiers (e.g. succeed-all) too.

    There's a special use of the colon character which users need to conform
    with too.
    """
    # test that each message validates correctly
    for message in messages:
        assert TaskMessageValidator.validate(message)[0] is valid

    # test that output validation is actually being performed
    id_ = flow({
        'scheduling': {
            'graph': {'R1': 'foo'}
        },
        'runtime': {
            'foo': {
                'outputs': {
                    str(random())[2:]: message
                    for message in messages
                }
            }
        },
    })
    val = lambda: validate(id_)
    if valid:
        val()
    else:
        with pytest.raises(WorkflowConfigError):
            val()


@pytest.mark.parametrize(
    'graph, expression, message', [
        pytest.param(
            'foo:x',
            'succeeded and (x or y)',
            r'foo:x is required in the graph.*'
            r' but optional in the completion expression',
            id='required-in-graph-optional-in-completion',
        ),
        pytest.param(
            'foo:x?',
            'succeeded and x',
            r'foo:x is optional in the graph.*'
            r' but required in the completion expression',
            id='optional-in-graph-required-in-completion',
        ),
        pytest.param(
            'foo:x',
            'succeeded',
            'foo:x is required in the graph.*'
            'but not referenced in the completion expression',
            id='required-in-graph-not-referenced-in-completion',
        ),
        pytest.param(
            # tests proposal point 4:
            # https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal
            'foo:expired',
            'succeeded',
            'foo:expired must be optional',
            id='expire-required-in-graph',
        ),
        pytest.param(
            'foo:expired?',
            'succeeded',
            'foo:expired is permitted in the graph.*'
            '\nTry: completion = "succeeded or expired"',
            id='expire-optional-in-graph-but-not-used-in-completion'
        ),
        pytest.param(
            # tests part of proposal point 5:
            # https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal
            'foo',
            'finished and x',
            '"finished" output cannot be used in completion expressions',
            id='finished-output-used-in-completion-expression',
        ),
        pytest.param(
            # https://github.com/cylc/cylc-flow/pull/6046#issuecomment-2059266086
            'foo?',
            'x and failed',
            'foo:failed is optional in the graph.*'
            'but required in the completion expression',
            id='failed-implicitly-optional-in-graph-required-in-completion',
        ),
        pytest.param(
            'foo',
            '(succeed and x) or failed',
            'Use "succeeded" not "succeed" in completion expressions',
            id='alt-compvar1',
        ),
        pytest.param(
            'foo? & foo:submitted?',
            'submit_fail or succeeded',
            'Use "submit_failed" not "submit_fail" in completion expressions',
            id='alt-compvar2',
        ),
        pytest.param(
            'foo? & foo:submitted?',
            'submit-failed or succeeded',
            'Use "submit_failed" rather than "submit-failed"'
            ' in completion expressions.',
            id='submit-failed used in completion expression',
        ),
        pytest.param(
            'foo:file-1',
            'succeeded or file-1',
            'Replace hyphens with underscores in task outputs when'
            ' used in completion expressions.',
            id='Hyphen used in completion expression',
        ),
        pytest.param(
            'foo:x',
            'not succeeded or x',
            'Error in .*'
            '\nInvalid expression',
            id='Non-whitelisted syntax used in completion expression',
        ),
      ]
)
def test_completion_expression_invalid(
    flow,
    validate,
    graph,
    expression,
    message,
):
    """It should ensure the completion is logically consistent with the graph.

    Tests proposal point 5:
    https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal
    """
    id_ = flow({
        'scheduling': {
            'graph': {'R1': graph},
        },
        'runtime': {
            'foo': {
                'completion': expression,
                'outputs': {
                    'x': 'xxx',
                    'y': 'yyy',
                    'file-1': 'asdf'
                },
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=message):
        validate(id_)


@pytest.mark.parametrize(
    'graph, expression', [
        ('foo', 'succeeded and (x or y or z)'),
        ('foo?', 'succeeded and (x or y or z) or failed or expired'),
        ('foo', '(succeeded and x) or (expired and y)'),
    ]
)
def test_completion_expression_valid(
    flow,
    validate,
    graph,
    expression,
):
    id_ = flow({
        'scheduling': {
            'graph': {'R1': graph},
        },
        'runtime': {
            'foo': {
                'completion': expression,
                'outputs': {
                    'x': 'xxx',
                    'y': 'yyy',
                    'z': 'zzz',
                },
            },
        },
    })
    validate(id_)


def test_completion_expression_cylc7_compat(
    flow,
    validate,
    monkeypatch
):
    id_ = flow({
        'scheduling': {
            'graph': {'R1': 'foo'},
        },
        'runtime': {
            'foo': {
                'completion': 'succeeded and x',
                'outputs': {
                    'x': 'xxx',
                },
            },
        },
    })
    monkeypatch.setattr('cylc.flow.flags.cylc7_back_compat', True)
    with pytest.raises(
        WorkflowConfigError,
        match="completion cannot be used in Cylc 7 compatibility mode."
    ):
        validate(id_)


def test_unique_messages(
    flow,
    validate
):
    """Task messages must be unique in the [outputs] section.

    See: https://github.com/cylc/cylc-flow/issues/6056
    """
    id_ = flow({
        'scheduling': {
            'graph': {'R1': 'foo'}
        },
        'runtime': {
            'foo': {
                'outputs': {
                    'a': 'foo',
                    'b': 'bar',
                    'c': 'baz',
                    'd': 'foo',
                }
            },
        }
    })

    with pytest.raises(
        WorkflowConfigError,
        match=(
            r'"\[runtime\]\[foo\]\[outputs\]d = foo"'
            ' - messages must be unique'
        ),
    ):
        validate(id_)

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
                'foo.bar',
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
                    str(random()): message
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

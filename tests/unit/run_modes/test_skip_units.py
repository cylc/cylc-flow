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
"""Unit tests for utilities supporting skip modes
"""
import pytest
from pytest import param, raises
from types import SimpleNamespace

from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.run_modes.skip import check_task_skip_config, process_outputs


@pytest.mark.parametrize(
    'conf',
    (
        param({}, id='no-skip-config'),
        param({'skip': {'outputs': []}}, id='no-skip-outputs'),
        param({'skip': {'outputs': ['foo1', 'failed']}}, id='ok-skip-outputs'),
    )
)
def test_good_check_task_skip_config(conf):
    """It returns none if the problems this function checks are not present.
    """
    tdef = SimpleNamespace(rtconfig=conf)
    tdef.name = 'foo'
    assert check_task_skip_config(tdef) is None


def test_raises_check_task_skip_config():
    """It raises an error if succeeded and failed are set.
    """
    tdef = SimpleNamespace(
        rtconfig={'skip': {'outputs': ['foo1', 'failed', 'succeeded']}}
    )
    tdef.name = 'foo'
    with raises(WorkflowConfigError, match='succeeded AND failed'):
        check_task_skip_config(tdef)


@pytest.mark.parametrize(
    'outputs, required, expect',
    (
        param([], [], ['succeeded'], id='implicit-succeded'),
        param(
            ['succeeded'], ['succeeded'], ['succeeded'],
            id='explicit-succeded'
        ),
        param(['submitted'], [], ['succeeded'], id='only-1-submit'),
        param(
            ['foo', 'bar', 'baz', 'qux'],
            ['bar', 'qux'],
            ['bar', 'qux', 'succeeded'],
            id='required-only'
        ),
        param(
            ['foo', 'baz'],
            ['bar', 'qux'],
            ['succeeded'],
            id='no-required'
        ),
        param(
            ['failed'],
            [],
            ['failed'],
            id='explicit-failed'
        ),
    )
)
def test_process_outputs(outputs, required, expect):
    """Check that skip outputs:

    1. Doesn't send submitted twice.
    2. Sends every required output.
    3. If failed is set send failed
    4. If failed in not set send succeeded.
    """
    # Create a mocked up task-proxy:
    rtconf = {'skip': {'outputs': outputs}}
    itask = SimpleNamespace(
        tdef=SimpleNamespace(
            rtconfig=rtconf),
        state=SimpleNamespace(
            outputs=SimpleNamespace(
                iter_required_messages=lambda exclude: iter(required),
                _message_to_trigger={v: v for v in required}
            )))

    assert process_outputs(itask, rtconf) == ['submitted', 'started'] + expect

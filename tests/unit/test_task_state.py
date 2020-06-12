# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

import pytest

from cylc.flow.taskdef import TaskDef
from cylc.flow.task_state import (
    TaskState,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_WAITING,
)


@pytest.mark.parametrize(
    'state,is_held',
    [
        (TASK_STATUS_WAITING, True),
        (TASK_STATUS_SUCCEEDED, False)
    ]
)
def test_state_comparison(state, is_held):
    """Test the __call__ method."""
    tdef = TaskDef('foo', {}, 'live', '123', True)
    tstate = TaskState(tdef, '123', state, is_held)

    assert tstate(state, is_held=is_held)
    assert tstate(state)
    assert tstate(is_held=is_held)
    assert tstate(state, 'of', 'flux')
    assert tstate(state, 'of', 'flux', is_held=is_held)

    assert not tstate(state + 'x', is_held=not is_held)
    assert not tstate(state, is_held=not is_held)
    assert not tstate(state + 'x', is_held=is_held)
    assert not tstate(state + 'x')
    assert not tstate(is_held=not is_held)
    assert not tstate(state + 'x', 'of', 'flux')


@pytest.mark.parametrize(
    'state,is_held,should_reset',
    [
        (None, None, False),
        (TASK_STATUS_WAITING, None, False),
        (None, True, False),
        (TASK_STATUS_WAITING, True, False),
        (TASK_STATUS_SUCCEEDED, None, True),
        (None, False, True),
        (TASK_STATUS_WAITING, False, True),
    ]
)
def test_reset(state, is_held, should_reset):
    """Test that tasks do or don't have their state changed."""
    tdef = TaskDef('foo', {}, 'live', '123', True)
    # create task state:
    #   * status: waiting
    #   * is_held: true
    tstate = TaskState(tdef, '123', TASK_STATUS_WAITING, True)
    assert tstate.reset(state, is_held) == should_reset
    if is_held is not None:
        assert tstate.is_held == is_held
    if state is not None:
        assert tstate.status == state


@pytest.mark.parametrize(
    'before,after,outputs',
    [
        (
            (TASK_STATUS_WAITING, False),
            (TASK_STATUS_SUCCEEDED, False),
            ['submitted', 'started', 'succeeded']
        ),
        (
            (TASK_STATUS_WAITING, False),
            (TASK_STATUS_FAILED, False),
            ['submitted', 'started', 'failed']
        ),
        (
            (TASK_STATUS_WAITING, False),
            (TASK_STATUS_FAILED, None),  # no change to is_held
            ['submitted', 'started', 'failed']
        ),
        (
            (TASK_STATUS_WAITING, False),
            (None, False),  # no change to status
            []
        ),
        # only reset task outputs if not setting task to held
        # https://github.com/cylc/cylc-flow/pull/2116
        (
            (TASK_STATUS_WAITING, False),
            (TASK_STATUS_FAILED, True),
            []
        ),
        # only reset task outputs if not setting task to held
        # https://github.com/cylc/cylc-flow/pull/2116
        (
            (TASK_STATUS_WAITING, False),
            (TASK_STATUS_SUCCEEDED, True),
            []
        )
    ]
)
def test_reset_outputs(before, after, outputs):
    """Test that outputs are reset correctly on state changes."""
    tdef = TaskDef('foo', {}, 'live', '123', True)

    orig_status, orig_is_held = before
    new_status, new_is_held = after

    tstate = TaskState(tdef, '123', orig_status, orig_is_held)
    assert tstate.outputs.get_completed() == []
    tstate.reset(status=new_status, is_held=new_is_held)
    assert tstate.outputs.get_completed() == outputs

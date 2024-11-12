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

import pytest
from types import SimpleNamespace

from cylc.flow.taskdef import TaskDef
from cylc.flow.cycling.integer import IntegerSequence, IntegerPoint
from cylc.flow.run_modes import RunMode, disable_task_event_handlers
from cylc.flow.task_trigger import Dependency, TaskTrigger
from cylc.flow.task_state import (
    TaskState,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
    TASK_STATUS_RUNNING,
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
    tdef = TaskDef('foo', {}, '123', '123')
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
    tdef = TaskDef('foo', {}, '123', '123')
    # create task state:
    #   * status: waiting
    #   * is_held: true
    tstate = TaskState(tdef, '123', TASK_STATUS_WAITING, True)
    assert tstate.reset(state, is_held) == should_reset
    if is_held is not None:
        assert tstate.is_held == is_held
    if state is not None:
        assert tstate.status == state


def test_task_prereq_duplicates(set_cycling_type):
    """Test prerequisite duplicates from multiple recurrences are discarded."""

    set_cycling_type()

    seq1 = IntegerSequence('R1', "1")
    seq2 = IntegerSequence('R/1/P1', "1")

    trig = TaskTrigger('a', "1", 'succeeded', None, None, None, None)

    dep = Dependency([trig], [trig], False)

    tdef = TaskDef('foo', {}, IntegerPoint("1"), IntegerPoint("1"))
    tdef.add_dependency(dep, seq1)
    tdef.add_dependency(dep, seq2)  # duplicate!

    tstate = TaskState(tdef, IntegerPoint("1"), TASK_STATUS_WAITING, False)

    prereqs = [p._satisfied for p in tstate.prerequisites]

    assert prereqs == [{("1", "a", "succeeded"): False}]


def test_task_state_order():
    """Test is_gt and is_gte methods."""

    tdef = TaskDef('foo', {}, IntegerPoint("1"), IntegerPoint("1"))
    tstate = TaskState(tdef, IntegerPoint("1"), TASK_STATUS_SUBMITTED, False)

    assert tstate.is_gt(TASK_STATUS_WAITING)
    assert tstate.is_gt(TASK_STATUS_PREPARING)
    assert tstate.is_gt(TASK_STATUS_SUBMIT_FAILED)
    assert not tstate.is_gt(TASK_STATUS_SUBMITTED)
    assert tstate.is_gte(TASK_STATUS_SUBMITTED)
    assert not tstate.is_gt(TASK_STATUS_RUNNING)
    assert not tstate.is_gte(TASK_STATUS_RUNNING)


@pytest.mark.parametrize(
    'itask_run_mode, disable_handlers, expect',
    (
        ('live', True, False),
        ('live', False, False),
        ('dummy', True, False),
        ('dummy', False, False),
        ('simulation', True, True),
        ('simulation', False, True),
        ('skip', True, True),
        ('skip', False, False),
    )
)
def test_disable_task_event_handlers(itask_run_mode, disable_handlers, expect):
    """Conditions under which task event handlers should not be used.
    """
    # Construct a fake itask object:
    itask = SimpleNamespace(
        run_mode=RunMode(itask_run_mode),
        platform={'disable task event handlers': disable_handlers},
        tdef=SimpleNamespace(
            rtconfig={
                'skip': {'disable task event handlers': disable_handlers}})
    )
    # Check method:
    assert disable_task_event_handlers(itask) is expect

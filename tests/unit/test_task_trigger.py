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

from cylc.flow.cycling.loader import get_point, get_sequence
from cylc.flow.exceptions import TriggerExpressionError
from cylc.flow.task_trigger import TaskTrigger, Dependency


def test_check_with_cycle_point():
    task_trigger = TaskTrigger(
        'fake_task_name', 1, 'fakeOutput', None, None, None, None)
    actual = str(task_trigger)
    expected = 'fake_task_name[1]:fakeOutput'
    assert actual == expected


def test_check_with_no_cycle_point_with_offset():
    task_trigger = TaskTrigger(
        'fake_task_name', 2, 'fakeOutput', None, None, None, None)
    actual = str(task_trigger)
    expected = 'fake_task_name[2]:fakeOutput'
    assert actual == expected


def test_check_with_no_cycle_point_or_offset():
    task_trigger = TaskTrigger(
        'fake_task_name', None, 'fakeOutput', None, None, None, None)
    actual = str(task_trigger)
    expected = 'fake_task_name:fakeOutput'
    assert actual == expected


def test_check_for_false_suicide():
    task_trigger = TaskTrigger(
        'fake_task_name', 1, 'fakeOutput', None, None, None, None)
    dependency = Dependency(
        [task_trigger, '&', task_trigger], [task_trigger], False)
    actual = str(dependency)
    expected = (
        '( fake_task_name[1]:fakeOutput ) ( & ) ( fake_task_name[1]'
        ':fakeOutput )')
    assert actual == expected


def test_check_for_true_suicide():
    task_trigger = TaskTrigger(
        'fake_task_name', None, 'fakeOutput', None, None, None, None)
    dependency = Dependency(
        [task_trigger, '&', task_trigger], [task_trigger], True)
    actual = str(dependency)
    expected = (
        '! ( fake_task_name:fakeOutput ) ( & ) ( fake_task_name:fakeOutput )')
    assert actual == expected


def test_check_for_list_of_lists_exp():
    task_trigger = TaskTrigger(
        'fake_task_name', None, 'fakeOutput', None, None, None, None)
    dependency = Dependency(
        [
            task_trigger,
            '&',
            ['task', '&', 'another_task']
        ],
        [task_trigger],
        False
    )
    actual = str(dependency)
    expected = (
        "( fake_task_name:fakeOutput ) ( & ) ['task', '&', 'another_task']")
    assert actual == expected


def test_check_exeption():
    with pytest.raises(TriggerExpressionError):
        TaskTrigger.get_trigger_name("Foo:Elephant")


def test_get_parent_point(cycling_mode):
    cycling_mode()

    one = get_point('1')
    two = get_point('2')

    trigger = TaskTrigger('name', None, 'output')
    assert trigger.get_parent_point(one) == one

    trigger = TaskTrigger('name', one, 'output', offset_is_absolute=True)
    assert trigger.get_parent_point(None) == one

    trigger = TaskTrigger('name', '+P1', 'output', initial_point=one)
    assert trigger.get_parent_point(one) == two

    trigger = TaskTrigger(
        'name', '+P1', 'output', offset_is_from_icp=True, initial_point=one)
    assert trigger.get_parent_point(two) == two
    assert trigger.get_parent_point(one) == two


def test_get_child_point(cycling_mode):
    cycling_mode()

    zero = get_point('0')
    one = get_point('1')
    two = get_point('2')
    p1 = get_sequence('P1', one)

    trigger = TaskTrigger('name', None, 'output')
    assert trigger.get_child_point(one, p1) == one
    assert trigger.get_child_point(two, p1) == two

    trigger = TaskTrigger('name', '+P1', 'output', offset_is_absolute=True)
    assert trigger.get_child_point(None, p1) == one

    trigger = TaskTrigger('name', '+P1', 'output', offset_is_from_icp=True)
    assert trigger.get_child_point(None, p1) == one

    trigger = TaskTrigger('name', '+P1', 'output', offset_is_irregular=True)
    assert trigger.get_child_point(one, p1) == zero

    trigger = TaskTrigger('name', '-P1', 'output', offset_is_irregular=True)
    assert trigger.get_child_point(one, p1) == two

    trigger = TaskTrigger('name', '+P1', 'output')
    assert trigger.get_child_point(one, None) == zero

    trigger = TaskTrigger('name', '-P1', 'output')
    assert trigger.get_child_point(one, None) == two


def test_get_point(cycling_mode):
    cycling_mode()

    one = get_point('1')
    two = get_point('2')

    trigger = TaskTrigger('name', '1', 'output', offset_is_absolute=True)
    assert trigger.get_point(None) == one

    trigger = TaskTrigger(
        'name', '+P1', 'output', offset_is_from_icp=True, initial_point=one)
    assert trigger.get_point(None) == two

    trigger = TaskTrigger('name', '+P1', 'output')
    assert trigger.get_point(one) == two

    trigger = TaskTrigger('name', None, 'output')
    assert trigger.get_point(one) == one


def test_str(cycling_mode):
    cycling_mode()

    one = get_point('1')
    two = get_point('2')

    trigger = TaskTrigger('name', '1', 'output', offset_is_absolute=True)
    assert str(trigger) == 'name[1]:output'

    trigger = TaskTrigger('name', '+P1', 'output')
    assert str(trigger) == 'name[+P1]:output'

    trigger = TaskTrigger('name', None, 'output')
    assert str(trigger) == 'name:output'

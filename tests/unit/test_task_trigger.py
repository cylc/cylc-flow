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

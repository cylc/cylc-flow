import pytest

from cylc.flow.exceptions import TriggerExpressionError
from cylc.flow.task_trigger import TaskTrigger, Dependency


def test_check_with_cycle_point():

    task_trigger = TaskTrigger('fake_task_name', '1', None, 'fakeOutput')

    actual = str(task_trigger)

    expected = 'fake_task_name[1]:fakeOutput'
    assert actual == expected


def test_check_with_no_cycle_point_with_offset():

    task_trigger = TaskTrigger('fake_task_name', None, 2, 'fakeOutput')

    actual = str(task_trigger)

    expected = 'fake_task_name[2]:fakeOutput'
    assert actual == expected


def test_check_with_no_cycle_point_or_offset():

    task_trigger = TaskTrigger('fake_task_name', None, None, 'fakeOutput')

    actual = str(task_trigger)

    expected = 'fake_task_name:fakeOutput'
    assert actual == expected


def test_check_for_false_suicide():

    task_trigger = TaskTrigger('fake_task_name', '1', None, 'fakeOutput')
    dependency = Dependency(
        [task_trigger, '&', task_trigger], [task_trigger], False)

    actual = str(dependency)

    expected = (
        '( fake_task_name[1]:fakeOutput ) ( & ) ( fake_task_name[1]'
        ':fakeOutput )')
    assert actual == expected


def test_check_for_true_suicide():

    task_trigger = TaskTrigger('fake_task_name', None, None, 'fakeOutput')
    dependency = Dependency(
        [task_trigger, '&', task_trigger], [task_trigger], True)

    actual = str(dependency)

    expected = (
        '! ( fake_task_name:fakeOutput ) ( & ) ( fake_task_name:fakeOutput )')
    assert actual == expected


def test_check_for_list_of_lists_exp():

    task_trigger = TaskTrigger('fake_task_name', None, None, 'fakeOutput')
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

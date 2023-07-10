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
"""Test the Cylc universal identifier system."""

import pytest

from cylc.flow.id import (
    LEGACY_CYCLE_SLASH_TASK,
    LEGACY_TASK_DOT_CYCLE,
    RELATIVE_ID,
    Tokens,
    UNIVERSAL_ID,
)


@pytest.mark.parametrize(
    'identifier',
    [
        '',
        '~',
        '~user//cycle'
        '~flow:state',
        'flow:flow_sel:flow_sel',
    ]
)
def test_univseral_id_illegal(identifier):
    """Test illegal formats of the universal identifier."""
    assert UNIVERSAL_ID.match(identifier) is None


@pytest.mark.parametrize(
    'identifier',
    [
        '~user',
        '~user/',
        '~user/workflow',
        '~user/workflow//',
        '~user/workflow:workflow_sel',
        '~user/workflow:workflow_sel//',
        '~user/workflow:workflow_sel//cycle',
        '~user/workflow:workflow_sel//cycle/',
        '~user/workflow:workflow_sel//cycle:cycle_sel',
        '~user/workflow:workflow_sel//cycle:cycle_sel/',
        '~user/workflow:workflow_sel//cycle:cycle_sel/task',
        '~user/workflow:workflow_sel//cycle:cycle_sel/task/',
        '~user/workflow:workflow_sel//cycle:cycle_sel/task:task_sel',
        '~user/workflow:workflow_sel//cycle:cycle_sel/task:task_sel/',
        '~user/workflow:workflow_sel//cycle:cycle_sel/task:task_sel/job',
        (
            '~user/workflow:workflow_sel//cycle:cycle_sel/task:task_sel/job'
            ':job_sel'
        ),
        'workflow',
        'workflow//',
        'workflow:workflow_sel',
        'workflow:workflow_sel//',
        'workflow:workflow_sel//cycle',
        'workflow:workflow_sel//cycle/',
        'workflow:workflow_sel//cycle:cycle_sel',
        'workflow:workflow_sel//cycle:cycle_sel/',
        'workflow:workflow_sel//cycle:cycle_sel/task',
        'workflow:workflow_sel//cycle:cycle_sel/task/',
        'workflow:workflow_sel//cycle:cycle_sel/task:task_sel',
        'workflow:workflow_sel//cycle:cycle_sel/task:task_sel/',
        'workflow:workflow_sel//cycle:cycle_sel/task:task_sel/job',
        'workflow:workflow_sel//cycle:cycle_sel/task:task_sel/job:job_sel'
    ]
)
def test_universal_id_matches(identifier):
    """test every legal format of the universal identifier."""
    # fmt: off
    expected_tokens = {
        'user':
            'user' if 'user' in identifier else None,
        'workflow':
            'workflow' if 'workflow' in identifier else None,
        'workflow_sel':
            'workflow_sel' if 'workflow_sel' in identifier else None,
        'cycle':
            'cycle' if 'cycle' in identifier else None,
        'cycle_sel':
            'cycle_sel' if 'cycle_sel' in identifier else None,
        'task':
            'task' if 'task' in identifier else None,
        'task_sel':
            'task_sel' if 'task_sel' in identifier else None,
        'job':
            'job' if 'job' in identifier else None,
        'job_sel':
            'job_sel' if 'job_sel' in identifier else None
    }
    # fmt: on
    match = UNIVERSAL_ID.match(identifier)
    assert match
    assert match.groupdict() == expected_tokens


@pytest.mark.parametrize(
    'identifier',
    [
        '~user/a/b/c',
        '~user/a/b/c//',
        '~user/a/b/c:workflow_sel',
        '~user/a/b/c:workflow_sel//',
        '~user/a/b/c:workflow_sel//cycle',
        '~user/a/b/c:workflow_sel//cycle/',
        '~user/a/b/c:workflow_sel//cycle:cycle_sel',
        '~user/a/b/c:workflow_sel//cycle:cycle_sel/',
        '~user/a/b/c:workflow_sel//cycle:cycle_sel/task',
        '~user/a/b/c:workflow_sel//cycle:cycle_sel/task/',
        '~user/a/b/c:workflow_sel//cycle:cycle_sel/task:task_sel',
        '~user/a/b/c:workflow_sel//cycle:cycle_sel/task:task_sel/',
        '~user/a/b/c:workflow_sel//cycle:cycle_sel/task:task_sel/job',
        (
            '~user/a/b/c:workflow_sel//cycle:cycle_sel/task:task_sel/job'
            ':job_sel'
        ),
        'a/b/c',
        'a/b/c//',
        'a/b/c:workflow_sel',
        'a/b/c:workflow_sel//',
        'a/b/c:workflow_sel//cycle',
        'a/b/c:workflow_sel//cycle/',
        'a/b/c:workflow_sel//cycle:cycle_sel',
        'a/b/c:workflow_sel//cycle:cycle_sel/',
        'a/b/c:workflow_sel//cycle:cycle_sel/task',
        'a/b/c:workflow_sel//cycle:cycle_sel/task/',
        'a/b/c:workflow_sel//cycle:cycle_sel/task:task_sel',
        'a/b/c:workflow_sel//cycle:cycle_sel/task:task_sel/',
        'a/b/c:workflow_sel//cycle:cycle_sel/task:task_sel/job',
        'a/b/c:workflow_sel//cycle:cycle_sel/task:task_sel/job:job_sel'
    ]
)
def test_universal_id_matches_hierarchical(identifier):
    """Test the UID with hierarchical workflow IDs."""
    # fmt: off
    expected_tokens = {
        'user':
            'user' if 'user' in identifier else None,
        'workflow':
            'a/b/c',  # the hierarchical workflow ID
        'workflow_sel':
            'workflow_sel' if 'workflow_sel' in identifier else None,
        'cycle':
            'cycle' if 'cycle' in identifier else None,
        'cycle_sel':
            'cycle_sel' if 'cycle_sel' in identifier else None,
        'task':
            'task' if 'task' in identifier else None,
        'task_sel':
            'task_sel' if 'task_sel' in identifier else None,
        'job':
            'job' if 'job' in identifier else None,
        'job_sel':
            'job_sel' if 'job_sel' in identifier else None
    }
    # fmt: on
    match = UNIVERSAL_ID.match(identifier)
    assert match
    assert match.groupdict() == expected_tokens


@pytest.mark.parametrize(
    'identifier',
    [
        '',
        '~',
        ':',
        'workflow//cycle',
        'task:task_sel:task_sel',
        'cycle/task'
        '//',
        '//~',
        '//:',
        '//workflow//cycle',
        '//task:task_sel:task_sel'
    ]
)
def test_relative_id_illegal(identifier):
    """Test illegal formats of the universal identifier."""
    assert RELATIVE_ID.match(identifier) is None


@pytest.mark.parametrize(
    'identifier',
    [
        '//cycle',
        '//cycle/',
        '//cycle:cycle_sel',
        '//cycle:cycle_sel/',
        '//cycle:cycle_sel/task',
        '//cycle:cycle_sel/task/',
        '//cycle:cycle_sel/task:task_sel',
        '//cycle:cycle_sel/task:task_sel/',
        '//cycle:cycle_sel/task:task_sel/job',
        '//cycle:cycle_sel/task:task_sel/job:job_sel',
    ]
)
def test_relative_id_matches(identifier):
    """test every legal format of the relative identifier."""
    expected_tokens = {
        'cycle': 'cycle' if 'cycle' in identifier else None,
        'cycle_sel': 'cycle_sel' if 'cycle_sel' in identifier else None,
        'task': 'task' if 'task' in identifier else None,
        'task_sel': 'task_sel' if 'task_sel' in identifier else None,
        'job': 'job' if 'job' in identifier else None,
        'job_sel': 'job_sel' if 'job_sel' in identifier else None
    }
    match = RELATIVE_ID.match(identifier)
    assert match
    assert match.groupdict() == expected_tokens


@pytest.mark.parametrize(
    'identifier',
    [
        '',
        '~',
        '/',
        ':',
        'task.cycle',  # the first digit of the cycle should be a number
        '//task.123',  # don't match the new format
        'task.cycle/job',
        'task:task_sel.123'  # selector should suffix the cycle
    ]
)
def test_legacy_task_dot_cycle_illegal(identifier):
    """Test illegal formats of the legacy task.cycle identifier."""
    assert LEGACY_TASK_DOT_CYCLE.match(identifier) is None


@pytest.mark.parametrize(
    'identifier,expected_tokens',
    [
        (
            'task.1',  # integer cycles can be one character long
            {'task': 'task', 'cycle': '1', 'task_sel': None}
        ),
        (
            't.a.s.k.123',
            {'task': 't.a.s.k', 'cycle': '123', 'task_sel': None}
        ),
        (
            'task.123:task_sel',
            {'task': 'task', 'cycle': '123', 'task_sel': 'task_sel'}
        ),
    ]
)
def test_legacy_task_dot_cycle_matches(identifier, expected_tokens):
    match = LEGACY_TASK_DOT_CYCLE.match(identifier)
    assert match
    assert match.groupdict() == expected_tokens


@pytest.mark.parametrize(
    'identifier',
    [
        '',
        '~',
        '/',
        ':',
        'cycle/task',  # the first digit of the cycle should be a number
        '//123/task',  # don't match the new format
        'cycle/task/job'
    ]
)
def test_legacy_cycle_slash_task_illegal(identifier):
    """Test illegal formats of the legacy cycle/task identifier."""
    assert LEGACY_CYCLE_SLASH_TASK.match(identifier) is None


@pytest.mark.parametrize(
    'identifier,expected_tokens',
    [
        (
            '123/task',
            {'task': 'task', 'cycle': '123', 'task_sel': None}
        ),
        (
            '123/t.a.s.k',
            {'task': 't.a.s.k', 'cycle': '123', 'task_sel': None}
        ),
        (
            '123/task:task_sel',
            {'task': 'task', 'cycle': '123', 'task_sel': 'task_sel'}
        )
    ]
)
def test_legacy_cycle_slash_task_matches(identifier, expected_tokens):
    match = LEGACY_CYCLE_SLASH_TASK.match(identifier)
    assert match
    assert match.groupdict() == expected_tokens


def test_tokens():
    # tested mainly in doctests

    Tokens('a')
    with pytest.raises(ValueError):
        Tokens('a', 'b')

    Tokens(cycle='a')
    with pytest.raises(ValueError):
        Tokens(foo='a')

    Tokens()['cycle'] = 'a'
    with pytest.raises(ValueError):
        Tokens()['foo'] = 'a'

    # test equality
    assert Tokens('a') == Tokens('a')
    assert Tokens('a') != Tokens('b')
    assert Tokens('a', relative=True) == Tokens('a', relative=True)
    assert Tokens('a', relative=True) != Tokens('b', relative=True)
    assert Tokens() != Tokens('a')
    assert Tokens(workflow='a') == Tokens('a')

    # test equality with non Tokens objects
    assert Tokens('a') != 'a'
    assert not Tokens('a') == 'a'
    assert Tokens('a') != 1
    assert not Tokens('a') == 1

    tokens = Tokens('a//b')
    tokens.update({'cycle': 'c', 'task': 'd'})
    assert tokens == Tokens('a//c/d')
    with pytest.raises(ValueError):
        tokens.update({'foo': 'c'})


def test_no_look_behind():
    """Ensure the UID pattern does not use lookbehinds.

    Ideally this pattern should be work for both cylc-flow and
    cylc-ui.

    2022-01-11:
        * Lookbehind support is at ~75%
        * https://caniuse.com/js-regexp-lookbehind

    """
    assert '?<=' not in UNIVERSAL_ID.pattern
    assert '?<!' not in UNIVERSAL_ID.pattern


def test_workflow_property():
    """The workflow property should provide the workflow part of the ID.

    The relevant selectors should be preserved
    """
    assert (
        Tokens('~u/w:ws//c:cs/t:ts/j:js').workflow
    ) == (
        Tokens('~u/w:ws')
    )


def test_task_property():
    """The task property should provide the task part of the ID.

    The relevant selectors should be preserved
    """
    assert (
        Tokens('~u/w:ws//c:cs/t:ts/j:js').task
    ) == (
        Tokens('//c:cs/t:ts/j:js', relative=True)
    )

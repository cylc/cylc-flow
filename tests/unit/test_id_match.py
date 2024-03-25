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

from typing import TYPE_CHECKING, Callable
from unittest.mock import create_autospec

import pytest

from cylc.flow.id import IDTokens, Tokens
from cylc.flow.id_match import filter_ids, point_match
from cylc.flow.task_pool import Pool
from cylc.flow.cycling.integer import IntegerPoint, CYCLER_TYPE_INTEGER
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.taskdef import TaskDef

if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase


def get_task_id(itask: TaskProxy) -> str:
    return f"{itask.tokens.relative_id}:{itask.state.status}"


@pytest.fixture
def task_pool(set_cycling_type: Callable):
    def _task_proxy(id_, hier):
        tokens = Tokens(id_, relative=True)
        hier = hier.get(tokens['task'], [])
        hier.append('root')
        tdef = create_autospec(TaskDef, namespace_hierarchy=hier)
        tdef.name = tokens['task']
        tdef.expiration_offset = None
        return TaskProxy(
            Tokens('~user/workflow'),
            tdef,
            start_point=IntegerPoint(tokens['cycle']),
            status=tokens['task_sel'],
        )

    def _task_pool(pool, hier) -> 'Pool':
        return {
            IntegerPoint(cycle): {
                id_.split(':')[0]: _task_proxy(id_, hier)
                for id_ in ids
            }
            for cycle, ids in pool.items()
        }

    set_cycling_type(CYCLER_TYPE_INTEGER)
    return _task_pool


@pytest.mark.parametrize(
    'ids,matched,not_matched',
    [
        (
            ['1'],
            ['1/a:x', '1/b:x', '1/c:x'],
            []
        ),
        (
            ['2'],
            [],
            ['2']
        ),
        (
            ['*'],
            ['1/a:x', '1/b:x', '1/c:x'],
            []
        ),
        (
            ['1/*'],
            ['1/a:x', '1/b:x', '1/c:x'],
            []
        ),
        (
            ['2/*'],
            [],
            ['2/*']
        ),
        (
            ['*/*'],
            ['1/a:x', '1/b:x', '1/c:x'],
            []
        ),
        (
            ['*/a'],
            ['1/a:x'],
            []
        ),
        (
            ['*/z'],
            [],
            ['*/z']
        ),
        (
            ['*/*:x'],
            ['1/a:x', '1/b:x', '1/c:x'],
            [],
        ),
        (
            ['*/*:y'],
            [],
            ['*/*:y'],
        ),
    ]
)
def test_filter_ids_task_mode(task_pool, ids, matched, not_matched):
    """Ensure tasks are returned in task mode."""
    pool = task_pool(
        {
            1: ['1/a:x', '1/b:x', '1/c:x']
        },
        {}
    )

    _matched, _not_matched = filter_ids(pool, ids)
    assert [get_task_id(itask) for itask in _matched] == matched
    assert _not_matched == not_matched


@pytest.mark.parametrize(
    'ids,matched,not_matched',
    [
        (
            ['1/a'],
            [1],
            [],
        ),
        (
            ['1/*'],
            [1],
            [],
        ),
        (
            ['1/*:x'],
            [1],
            [],
        ),
        (
            ['1/*:y'],
            [],
            ['1/*:y'],
        ),
        (
            ['*/*:x'],
            [1],
            [],
        ),
        (
            ['1/z'],
            [],
            ['1/z'],
        ),
        (
            ['1'],
            [1],
            [],
        ),
        (
            ['3'],
            [],
            ['3'],
        ),
    ]
)
def test_filter_ids_cycle_mode(task_pool, ids, matched, not_matched):
    """Ensure cycle poinds are returned in cycle mode."""
    pool = task_pool(
        {
            1: ['1/a:x', '1/b:x'],
            2: ['1/a:x'],
            3: [],
        },
        {}
    )

    _matched, _not_matched = filter_ids(pool, ids, out=IDTokens.Cycle)
    assert _matched == [IntegerPoint(i) for i in matched]
    assert _not_matched == not_matched


def test_filter_ids_invalid(caplog):
    """Ensure invalid IDs are handled elegantly."""
    matched, not_matched = filter_ids({}, ['#'])
    assert matched == []
    assert not_matched == ['#']
    assert caplog.record_tuples == [
        ('cylc', 30, 'No active tasks matching: #'),
    ]
    caplog.clear()
    matched, not_matched = filter_ids({}, ['#'], warn=False)
    assert caplog.record_tuples == []


def test_filter_ids_pattern_match_off(task_pool):
    """Ensure filtering works when pattern matching is turned off."""
    pool = task_pool(
        {
            1: ['1/a:x'],
        },
        {}
    )

    _matched, _not_matched = filter_ids(
        pool,
        ['1/a'],
        out=IDTokens.Task,
        pattern_match=False,
    )
    assert [get_task_id(itask) for itask in _matched] == ['1/a:x']
    assert _not_matched == []


def test_filter_ids_toggle_pattern_matching(task_pool, caplog):
    """Ensure pattern matching can be toggled on and off."""
    pool = task_pool(
        {
            1: ['1/a:x'],
        },
        {}
    )

    ids = ['*/*']

    # ensure pattern matching works
    _matched, _not_matched = filter_ids(
        pool,
        ids,
        out=IDTokens.Task,
        pattern_match=True,
    )
    assert [get_task_id(itask) for itask in _matched] == ['1/a:x']
    assert _not_matched == []

    # ensure pattern matching can be disabled
    caplog.clear()
    _matched, _not_matched = filter_ids(
        pool,
        ids,
        out=IDTokens.Task,
        pattern_match=False,
    )
    assert [get_task_id(itask) for itask in _matched] == []
    assert _not_matched == ['*/*']

    # ensure the ID is logged
    assert len(caplog.record_tuples) == 1
    assert '*/*' in caplog.record_tuples[0][2]


@pytest.mark.parametrize(
    'ids,matched,not_matched',
    [
        (['1/A'], ['1/a:x'], []),
        (['1/B'], ['1/b1:x', '1/b2:x'], []),
        (['1/C'], [], ['1/C']),
        (['1/root'], ['1/a:x', '1/b1:x', '1/b2:x'], []),
    ]
)
def test_filter_ids_namespace_hierarchy(task_pool, ids, matched, not_matched):
    """Ensure matching includes namespaces."""
    pool = task_pool(
        {
            1: ['1/a:x', '1/b1:x', '1/b2:x']
        },
        {
            'a': ['A'],
            'b1': ['B'],
            'b2': ['B'],
        },
    )

    _matched, _not_matched = filter_ids(
        pool,
        ids,
        pattern_match=False,
    )

    assert [get_task_id(itask) for itask in _matched] == matched
    assert _not_matched == not_matched


def test_filter_ids_out_format():
    filter_ids({}, [], out=IDTokens.Cycle)
    with pytest.raises(ValueError):
        filter_ids({}, [], out=IDTokens.Job)


def test_filter_ids_log_errors(caplog):
    _, _not_matched = filter_ids({}, ['/////'])
    assert _not_matched == ['/////']
    assert caplog.record_tuples == [('cylc', 30, 'Invalid ID: /////')]


@pytest.mark.parametrize(
    'point, value, pattern_match, expected',
    [
        (IntegerPoint(23), '23', True, True),
        (IntegerPoint(23), '23', False, True),
        (IntegerPoint(23), '2*', True, True),
        (IntegerPoint(23), '2*', False, False),
        (IntegerPoint(23), '2a', True, False),
        (ISO8601Point('2049-01-01T00:00Z'), '2049', True, True),
        (ISO8601Point('2049-01-01T00:00Z'), '2049', False, True),
        (ISO8601Point('2049-03-01T00:00Z'), '2049', True, False),
        (ISO8601Point('2049-03-01T00:00Z'), '2049*', True, True),
        (ISO8601Point('2049-03-01T00:00Z'), '2049*', False, False),
        (ISO8601Point('2049-01-01T00:00Z'), '20490101T00Z', False, True),
        (ISO8601Point('2049-01-01T00:00Z'), '20490101T03+03', False, True),
        (ISO8601Point('2049-01-01T00:00Z'), '2049a', True, False),
    ]
)
def test_point_match(
    point: 'PointBase', value: str, pattern_match: bool, expected: bool,
    set_cycling_type: Callable
):
    set_cycling_type(point.TYPE, time_zone='Z')
    assert point_match(point, value, pattern_match) is expected

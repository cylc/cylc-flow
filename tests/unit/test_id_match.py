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

from textwrap import dedent
from types import SimpleNamespace
from typing import TYPE_CHECKING, Set, Tuple, cast

import pytest

from cylc.flow.id import Tokens
from cylc.flow.id_match import id_match
from cylc.flow.config import WorkflowConfig

if TYPE_CHECKING:
    from cylc.flow.id_match import TaskTokens


def to_tokens(*ids):
    return cast('Set[TaskTokens]', {Tokens(id_, relative=True) for id_ in ids})


def to_string_ids(*ids):
    return {id_.relative_id for id_ in ids}


def to_string_ids_with_selectors(*ids):
    return {id_.relative_id_with_selectors for id_ in ids}


@pytest.fixture
def test_config(tmp_path):
    path = tmp_path / 'flow.cylc'
    with open(path, 'w+') as flow_cylc:
        flow_cylc.write(dedent('''
            [scheduler]
                allow implicit tasks = True

            [scheduling]
                cycling mode = integer
                initial cycle point = 1
                [[graph]]
                    P1 = a => b => c => d
                    P3 = z
        '''))

    return WorkflowConfig('test', str(path), SimpleNamespace())


def _id_match(
    config: 'WorkflowConfig',
    pool: 'Set[TaskTokens]',
    ids: 'Set[TaskTokens]',
    only_match_pool: bool = False,
) -> 'Tuple[Set[str], Set[str]]':
    """Convenience function for testing, converts strings to tokens."""
    matched, unmatched = id_match(
        config,
        pool,
        to_tokens(*ids),
        only_match_pool=only_match_pool,
    )
    return (
        to_string_ids(*matched),
        to_string_ids_with_selectors(*unmatched),
    )


@pytest.mark.parametrize(
    'ids,matched,unmatched',
    [
        (
            {'1'},
            {'1/a', '1/b', '1/c'},
            set(),
        ),
        (
            {'2'},
            set(),
            {'2'}
        ),
        (
            {'*'},
            {'1/a', '1/b', '1/c'},
            set(),
        ),
        (
            {'1/*'},
            {'1/a', '1/b', '1/c'},
            set(),
        ),
        (
            {'2/*'},
            set(),
            {'2/*'}
        ),
        (
            {'*/*'},
            {'1/a', '1/b', '1/c'},
            set(),
        ),
        (
            {'*/a'},
            {'1/a'},
            set(),
        ),
        (
            {'*/z'},
            set(),
            {'*/z'}
        ),
        (
            {'*/*:x'},
            {'1/a', '1/b', '1/c'},
            set(),
        ),
        (
            {'*/*:y'},
            set(),
            {'*/*:y'},
        ),
    ]
)
def test_match_task(test_config, ids, matched, unmatched):
    """It should match task IDs."""
    pool = to_tokens('1/a:x', '1/b:x', '1/c:x')
    _matched, _unmatched = _id_match(
        test_config,
        pool,
        ids,
        only_match_pool=True,
    )
    assert _matched == matched
    assert _unmatched == unmatched


@pytest.mark.parametrize(
    'ids,matched,unmatched',
    [
        (
            {'1/a'},
            {'1/a'},
            set(),
        ),
        (
            {'1/*'},
            {'1/a', '1/b'},
            set(),
        ),
        (
            {'1/*:x'},
            {'1/a', '1/b'},
            set(),
        ),
        (
            {'1/*:y'},
            set(),
            {'1/*:y'},
        ),
        (
            {'*/*:x'},
            {'1/a', '1/b', '2/a'},
            set(),
        ),
        (
            {'1/z'},
            set(),
            {'1/z'},
        ),
        (
            {'1'},
            {'1/a', '1/b'},
            set(),
        ),
        (
            {'3'},
            set(),
            {'3'},
        ),
    ]
)
def test_match_cycle(test_config, ids, matched, unmatched):
    """It should match cycle IDs."""
    pool = to_tokens('1/a:x', '1/b:x', '2/a:x')
    assert _id_match(
        test_config,
        pool,
        ids,
        only_match_pool=True,
    ) == (matched, unmatched)


@pytest.mark.parametrize(
    'ids,matched,unmatched',
    [
        (
            {'1/root'},
            {'1/a', '1/b', '1/c', '1/d', '1/z'},
            set(),
        ),
        (
            {'2/root'},
            {'2/a', '2/b', '2/c', '2/d'},  # 1/z isn't in cycle 2
            set(),
        ),
        (
            {'*/root'},
            # should match all active cycles (i.e. cycles 1 and 2)
            {'1/a', '1/b', '1/c', '1/d', '1/z', '2/a', '2/b', '2/c', '2/d'},
            set(),
        ),
        (
            {'1/[ad]'},
            {'1/a', '1/d'},
            set(),
        ),
        (
            {'1/[!ad]'},
            {'1/b', '1/c', '1/z'},
            set(),
        ),
    ]
)
def test_match_inactive(test_config, ids, matched, unmatched):
    """It should match non-pool tasks"""
    assert _id_match(
        test_config,
        to_tokens('1/a:running', '2/a:waiting'),  # active cycles are 1 and 2
        ids,
    ) == (matched, unmatched)


@pytest.mark.parametrize(
    'ids,matched,unmatched',
    [
        ({'1/A'}, {'1/a'}, set()),
        ({'1/B'}, {'1/b1', '1/b2'}, set()),
        ({'1/C'}, set(), {'1/C'}),
        ({'1/root'}, {'1/a', '1/b1', '1/b2'}, set()),
    ]
)
def test_match_family(tmp_path, ids, matched, unmatched):
    """It should match family IDs."""
    pool = to_tokens('1/a:x', '1/b1:x', '1/b2:x')

    path = tmp_path / 'flow.cylc'
    with open(path, 'w+') as flow_cylc:
        flow_cylc.write(dedent('''
            [scheduling]
                cycling mode = integer
                initial cycle point = 1
                [[graph]]
                    P1 = a & b1 & b2
            [runtime]
                [[a]]
                    inherit = A
                [[b1, b2]]
                    inherit = B
                [[A, B]]
        '''))
    config = WorkflowConfig('test', str(path), SimpleNamespace())

    assert _id_match(config, pool, ids) == (matched, unmatched)

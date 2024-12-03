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

from functools import partial
from typing import Optional

import pytest

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.cycling.loader import ISO8601_CYCLING_TYPE, get_point
from cylc.flow.id import Tokens, detokenise
from cylc.flow.prerequisite import Prerequisite, SatisfiedState
from cylc.flow.run_modes import RunMode


detok = partial(detokenise, selectors=True, relative=True)


@pytest.fixture
def prereq(set_cycling_type):
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    prereq = Prerequisite(get_point('2000'))
    prereq[(1999, 'a', 'succeeded')] = True
    prereq[(2000, 'b', 'succeeded')] = False
    prereq[(2000, 'c', 'succeeded')] = False
    prereq[(2001, 'd', 'custom')] = False
    return prereq


def test_satisfied(prereq: Prerequisite):
    assert prereq._satisfied == {
        # the pre-initial dependency should be marked as satisfied
        ('1999', 'a', 'succeeded'): 'satisfied naturally',
        # all others should not
        ('2000', 'b', 'succeeded'): False,
        ('2000', 'c', 'succeeded'): False,
        ('2001', 'd', 'custom'): False,
    }
    # No cached satisfaction state yet:
    assert prereq._cached_satisfied is None
    # Calling self.is_satisfied() should cache the result:
    assert not prereq.is_satisfied()
    assert prereq._cached_satisfied is False

    # mark two prerequisites as satisfied
    prereq.satisfy_me([
        Tokens('2000/b:succeeded', relative=True),
        Tokens('2000/c:succeeded', relative=True),
    ])
    assert prereq._satisfied == {
        # the pre-initial dependency should be marked as satisfied
        ('1999', 'a', 'succeeded'): 'satisfied naturally',
        # the two newly-satisfied dependency should be satisfied
        ('2000', 'b', 'succeeded'): 'satisfied naturally',
        ('2000', 'c', 'succeeded'): 'satisfied naturally',
        # the remaining dependency should not
        ('2001', 'd', 'custom'): False,
    }
    # Should have reset cached satisfaction state:
    assert prereq._cached_satisfied is None
    assert not prereq.is_satisfied()

    # mark all prereqs as satisfied
    prereq.set_satisfied()
    assert prereq._satisfied == {
        # the pre-initial dependency should be marked as satisfied
        ('1999', 'a', 'succeeded'): 'satisfied naturally',
        # the two newly-satisfied dependency should be satisfied
        ('2000', 'b', 'succeeded'): 'satisfied naturally',
        ('2000', 'c', 'succeeded'): 'satisfied naturally',
        # the remaining dependency should be marked as forse-satisfied
        ('2001', 'd', 'custom'): 'force satisfied',
    }
    # Should have set cached satisfaction state as must be true now:
    assert prereq._cached_satisfied is True
    assert prereq.is_satisfied()


def test_getitem_setitem(prereq: Prerequisite):
    msg = ('2000', 'b', 'succeeded')
    # __getitem__:
    assert prereq[msg] is False

    # __setitem__:
    prereq[msg] = True
    assert prereq[msg] == 'satisfied naturally'
    prereq[msg] = 'force satisfied'
    assert prereq[msg] == 'force satisfied'
    # coercion of cycle point
    assert prereq[(2000, 'b', 'succeeded')] == 'force satisfied'
    assert prereq[(get_point('2000'), 'b', 'succeeded')] == 'force satisfied'


def test_iter(prereq: Prerequisite):
    assert list(prereq) == [
        ('1999', 'a', 'succeeded'),
        ('2000', 'b', 'succeeded'),
        ('2000', 'c', 'succeeded'),
        ('2001', 'd', 'custom'),
    ]
    assert [p.task for p in prereq] == ['a', 'b', 'c', 'd']


def test_items(prereq: Prerequisite):
    assert list(prereq.items()) == [
        (('1999', 'a', 'succeeded'), 'satisfied naturally'),
        (('2000', 'b', 'succeeded'), False),
        (('2000', 'c', 'succeeded'), False),
        (('2001', 'd', 'custom'), False),
    ]


def test_set_conditional_expr(prereq: Prerequisite):
    assert not prereq.is_satisfied()
    prereq.set_conditional_expr('1999/a succeeded | 2000/b succeeded')
    assert prereq.is_satisfied()


def test_iter_target_point_strings(prereq):
    assert set(prereq.iter_target_point_strings()) == {
        '1999',
        '2000',
        '2001',
    }


def test_get_target_points(prereq):
    assert set(prereq.get_target_points()) == {
        get_point('1999'),
        get_point('2000'),
        get_point('2001'),
    }


@pytest.fixture
def satisfied_states_prereq():
    """Fixture for testing the full range of possible satisfied states."""
    prereq = Prerequisite(IntegerPoint('2'))
    prereq[('1', 'a', 'x')] = True
    prereq[('1', 'b', 'x')] = False
    prereq[('1', 'c', 'x')] = 'satisfied from database'
    prereq[('1', 'd', 'x')] = 'force satisfied'
    prereq[('1', 'e', 'x')] = 'satisfied by skip mode'
    return prereq


def test_unset_naturally_satisfied(satisfied_states_prereq: Prerequisite):
    satisfied_states_prereq[('1', 'a', 'y')] = True
    satisfied_states_prereq[('1', 'a', 'z')] = 'force satisfied'
    for id_, expected in [
        ('1/a', True),
        ('1/b', False),
        ('1/c', True),
        ('1/d', False),
        ('1/e', True),
    ]:
        assert (
            satisfied_states_prereq.unset_naturally_satisfied(id_) == expected
        )
    assert satisfied_states_prereq._satisfied == {
        ('1', 'a', 'x'): False,
        ('1', 'a', 'y'): False,
        ('1', 'a', 'z'): 'force satisfied',
        ('1', 'b', 'x'): False,
        ('1', 'c', 'x'): False,
        ('1', 'd', 'x'): 'force satisfied',
        ('1', 'e', 'x'): False,
    }


def test_set_satisfied(satisfied_states_prereq: Prerequisite):
    satisfied_states_prereq.set_satisfied()
    assert satisfied_states_prereq._satisfied == {
        ('1', 'a', 'x'): 'satisfied naturally',
        ('1', 'b', 'x'): 'force satisfied',
        ('1', 'c', 'x'): 'satisfied from database',
        ('1', 'd', 'x'): 'force satisfied',
        ('1', 'e', 'x'): 'satisfied by skip mode',
    }


def test_satisfy_me():
    prereq = Prerequisite(IntegerPoint('2'))
    for task_name in ('a', 'b', 'c'):
        prereq[('1', task_name, 'x')] = False
    assert not prereq.is_satisfied()
    assert prereq._cached_satisfied is False

    valid = prereq.satisfy_me(
        [Tokens('//1/a:x'), Tokens('//1/d:x'), Tokens('//1/c:y')],
    )
    assert {detok(tokens) for tokens in valid} == {'1/a:x'}
    assert prereq._satisfied == {
        ('1', 'a', 'x'): 'satisfied naturally',
        ('1', 'b', 'x'): False,
        ('1', 'c', 'x'): False,
    }
    # should have reset cached satisfaction state
    assert prereq._cached_satisfied is None

    valid = prereq.satisfy_me(
        [Tokens('//1/a:x'), Tokens('//1/b:x')],
        forced=True,
    )
    assert {detok(tokens) for tokens in valid} == {'1/a:x', '1/b:x'}
    assert prereq._satisfied == {
        # 1/a:x unaffected as already satisfied
        ('1', 'a', 'x'): 'satisfied naturally',
        ('1', 'b', 'x'): 'force satisfied',
        ('1', 'c', 'x'): False,
    }


@pytest.mark.parametrize('forced, mode, expected', [
    (False, None, 'satisfied naturally'),
    (True, None, 'force satisfied'),
    (True, RunMode.SKIP, 'force satisfied'),
    (False, RunMode.SKIP, 'satisfied by skip mode'),
])
def test_satisfy_me__override_false(
    forced: bool,
    mode: Optional[RunMode],
    expected: SatisfiedState,
):
    """Test satisfying an unsatisfied prereq with different states."""
    prereq = Prerequisite(IntegerPoint('2'))
    prereq[('1', 'a', 'x')] = False

    prereq.satisfy_me([Tokens('//1/a:x')], forced=forced, mode=mode)
    assert prereq[('1', 'a', 'x')] == expected


@pytest.mark.parametrize('mode', [None, RunMode.SKIP])
@pytest.mark.parametrize('forced', [True, False])
@pytest.mark.parametrize('existing', [
    'satisfied from database',
    'force satisfied',
    'satisfied naturally',
])
def test_satisfy_me__override_truthy(
    existing: SatisfiedState,
    forced: bool,
    mode: Optional[RunMode],
):
    """Test that satisfying an already-satisfied prereq doesn't change it."""
    prereq = Prerequisite(IntegerPoint('2'))
    prereq[('1', 'a', 'x')] = existing

    prereq.satisfy_me([Tokens('//1/a:x')], forced=forced, mode=mode)
    assert prereq[('1', 'a', 'x')] == existing

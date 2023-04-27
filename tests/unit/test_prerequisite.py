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

from cylc.flow.cycling.loader import ISO8601_CYCLING_TYPE, get_point
from cylc.flow.prerequisite import Prerequisite


@pytest.fixture
def prereq(set_cycling_type):
    set_cycling_type(ISO8601_CYCLING_TYPE, "Z")
    prereq = Prerequisite(
        get_point('2000'),
        start_point=get_point('2000')
    )
    prereq.add(
        'a',
        '1999',
        'succeeded',
        True
    )
    prereq.add(
        'b',
        '2000',
        'succeeded',
        False
    )
    prereq.add(
        'c',
        '2000',
        'succeeded',
        False
    )
    prereq.add(
        'd',
        '2001',
        'custom',
        False
    )
    return prereq


def test_satisfied(prereq):
    assert prereq.satisfied == {
        # the pre-initial dependency should be marked as satisfied
        ('1999', 'a', 'succeeded'): 'satisfied naturally',
        # all others should not
        ('2000', 'b', 'succeeded'): False,
        ('2000', 'c', 'succeeded'): False,
        ('2001', 'd', 'custom'): False,
    }
    # mark two prerequisites as satisfied
    prereq.satisfy_me({
        ('2000', 'b', 'succeeded'),
        ('2000', 'c', 'succeeded'),
    })
    assert prereq.satisfied == {
        # the pre-initial dependency should be marked as satisfied
        ('1999', 'a', 'succeeded'): 'satisfied naturally',
        # the two newly-satisfied dependency should be satisfied
        ('2000', 'b', 'succeeded'): 'satisfied naturally',
        ('2000', 'c', 'succeeded'): 'satisfied naturally',
        # the remaining dependency should not
        ('2001', 'd', 'custom'): False,
    }
    # mark all prereqs as satisfied
    prereq.set_satisfied()
    assert prereq.satisfied == {
        # the pre-initial dependency should be marked as satisfied
        ('1999', 'a', 'succeeded'): 'satisfied naturally',
        # the two newly-satisfied dependency should be satisfied
        ('2000', 'b', 'succeeded'): 'satisfied naturally',
        ('2000', 'c', 'succeeded'): 'satisfied naturally',
        # the remaining dependency should be marked as forse-satisfied
        ('2001', 'd', 'custom'): 'force satisfied',
    }
    # mark all prereqs as unsatisfied
    prereq.set_not_satisfied()
    assert prereq.satisfied == {
        # all prereqs INCLUDING the pre-initial should be marked as nnot
        # satisfied
        ('1999', 'a', 'succeeded'): False,
        ('2000', 'b', 'succeeded'): False,
        ('2000', 'c', 'succeeded'): False,
        ('2001', 'd', 'custom'): False,
    }


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

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

from cylc.flow.cycling import (
    SequenceBase,
    IntervalBase,
    PointBase,
    parse_exclusion,
)

from cylc.flow.cycling.integer import (
    IntegerPoint,
    IntegerSequence,
)

from cylc.flow.cycling.iso8601 import (
    ISO8601Point,
    ISO8601Sequence,
)

from cylc.flow.cycling.loader import (
    INTEGER_CYCLING_TYPE,
    ISO8601_CYCLING_TYPE,
)


def test_simple_abstract_class_test():
    """Cannot instantiate abstract classes, they must be defined in
    the subclasses"""
    with pytest.raises(TypeError):
        SequenceBase('sequence-string', 'context_string')
    with pytest.raises(TypeError):
        IntervalBase('value')
    with pytest.raises(TypeError):
        PointBase('value')


def test_parse_exclusion_simple():
    """Tests the simple case of exclusion parsing"""
    expression = "PT1H!20000101T02Z"
    sequence, exclusion = parse_exclusion(expression)
    assert sequence == "PT1H"
    assert exclusion == ['20000101T02Z']


def test_parse_exclusions_list():
    """Tests the simple case of exclusion parsing"""
    expression = "PT1H!(T03, T06, T09)"
    sequence, exclusion = parse_exclusion(expression)
    assert sequence == "PT1H"
    assert exclusion == ['T03', 'T06', 'T09']


def test_parse_exclusions_list_spaces():
    """Tests the simple case of exclusion parsing"""
    expression = "PT1H!    (T03, T06,   T09)   "
    sequence, exclusion = parse_exclusion(expression)
    assert sequence == "PT1H"
    assert exclusion == ['T03', 'T06', 'T09']


@pytest.mark.parametrize(
    'expression',
    [
        'T01/PT1H!(T06, T09), PT5M',
        'T01/PT1H!T03, PT17H, (T06, T09), PT5M',
        'T01/PT1H! PT8H, (T06, T09)',
        'T01/PT1H! T03, T06, T09',
        'T01/PT1H !T03 !T06',
    ],
)
def test_parse_bad_exclusion(expression):
    """Tests incorrectly formatted exclusions"""
    with pytest.raises(Exception):
        parse_exclusion(expression)


@pytest.mark.parametrize(
    'sequence, wf_start_point, expected',
    (
        (
            ('R/2/P2', 1),
            None,
            [2,4,6,8,10]
        ),
        (
            ('R/2/P2', 1),
            3,
            [4,6,8,10,12]
        ),
    ),
)
def test_get_first_n_points_integer(
    set_cycling_type,
    sequence, wf_start_point, expected
):
    """Test sequence get_first_n_points method.

    (The method is implemented in the base class).
    """
    set_cycling_type(INTEGER_CYCLING_TYPE)
    sequence = IntegerSequence(*sequence)
    if wf_start_point is not None:
        wf_start_point = IntegerPoint(wf_start_point)
    expected = [
        IntegerPoint(p)
        for p in expected
    ]
    assert (
        expected == (
            sequence.get_first_n_points(
                len(expected),
                wf_start_point
            )
        )
    )


@pytest.mark.parametrize(
    'sequence, wf_start_point, expected',
    (
        (
            ('R/2008/P2Y', '2001'),
            None,
            ['2008', '2010', '2012', '2014', '2016']
        ),
        (
            ('R/2008/P2Y', '2001'),
            '2009',
            ['2010', '2012', '2014', '2016', '2018']
        ),
    ),
)
def test_get_first_n_points_iso8601(
    set_cycling_type,
    sequence, wf_start_point, expected
):
    """Test sequence get_first_n_points method.

    (The method is implemented in the base class).
    """
    set_cycling_type(ISO8601_CYCLING_TYPE, 'Z')
    sequence = ISO8601Sequence(*sequence)
    if wf_start_point is not None:
        wf_start_point = ISO8601Point(wf_start_point)
    expected = [
        ISO8601Point(p)
        for p in expected
    ]

    assert (
        expected == (
            sequence.get_first_n_points(
                len(expected),
                wf_start_point
            )
        )
    )

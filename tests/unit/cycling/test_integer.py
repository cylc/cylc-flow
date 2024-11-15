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

from cylc.flow.cycling.integer import (
    IntegerSequence,
    IntegerPoint,
    IntegerInterval,
    IntervalParsingError,
    SequenceParsingError,
)
from cylc.flow.cycling.iso8601 import (
    ISO8601Point,
    ISO8601Interval,
)
from cylc.flow.exceptions import CyclerTypeError


def test_exclusions_simple():
    """Test the generation of points for integer sequences with exclusions.
    """
    sequence = IntegerSequence('R/P1!3', 1, 5)
    output = []
    point = sequence.get_start_point()
    while point:
        output.append(point)
        point = sequence.get_next_point(point)
    assert [int(out) for out in output] == [1, 2, 4, 5]


def test_multiple_exclusions_simple():
    """Tests the multiple exclusion syntax for integer notation"""
    sequence = IntegerSequence('R/P1!(2,3,7)', 1, 10)
    output = []
    point = sequence.get_start_point()
    while point:
        output.append(point)
        point = sequence.get_next_point(point)
    assert [int(out) for out in output] == [1, 4, 5, 6, 8, 9, 10]

    # duplicate excluded points should be ignored
    sequence1 = IntegerSequence('R/P1!(2,2,2)', 1, 10)
    sequence2 = IntegerSequence('R/P1!(2)', 1, 10)
    assert (
        sequence1.exclusions.exclusion_points
    ) == sequence2.exclusions.exclusion_points


def test_multiple_exclusions_integer_sequence():
    """Tests the multiple exclusion syntax for integer notation"""
    sequence = IntegerSequence('P1 ! P2', 1, 10)
    output = []
    point = sequence.get_start_point()
    while point:
        output.append(point)
        point = sequence.get_next_point(point)
    assert [int(out) for out in output] == [2, 4, 6, 8, 10]
    assert sequence.exclusions[0] == IntegerSequence('P2', 1, 10)


def test_multiple_exclusions_integer_sequence2():
    """Tests the multiple exclusion syntax for integer notation"""
    sequence = IntegerSequence('P1 ! +P1/P2', 1, 10)
    output = []
    point = sequence.get_start_point()
    while point:
        output.append(point)
        point = sequence.get_next_point(point)
    assert [int(out) for out in output] == [1, 3, 5, 7, 9]


def test_multiple_exclusions_integer_sequence3():
    """Tests the multiple exclusion syntax for integer notation"""
    sequence = IntegerSequence('P1 ! (P2, 6, 8) ', 1, 10)
    output = []
    point = sequence.get_start_point()
    while point:
        output.append(point)
        point = sequence.get_next_point(point)
    assert [int(out) for out in output] == [2, 4, 10]


def test_multiple_exclusions_integer_sequence_weird_valid_formatting():
    """Tests the multiple exclusion syntax for integer notation"""
    sequence = IntegerSequence('P1 !(P2,     6,8) ', 1, 10)
    output = []
    point = sequence.get_start_point()
    while point:
        output.append(point)
        point = sequence.get_next_point(point)
    assert [int(out) for out in output] == [2, 4, 10]


def test_multiple_exclusions_integer_sequence_invalid_formatting():
    """Tests the multiple exclusion syntax for integer notation"""
    with pytest.raises(Exception):
        IntegerSequence('P1 !(6,8), P2 ', 1, 10)


def test_multiple_exclusions_extensive():
    """Tests IntegerSequence methods for sequences with multi-exclusions"""
    points = [IntegerPoint(i) for i in range(10)]
    sequence = IntegerSequence('R/P1!(2,3,7)', 1, 10)
    assert not sequence.is_on_sequence(points[3])
    assert not sequence.is_valid(points[3])
    assert sequence.get_prev_point(points[3]) == points[1]
    assert sequence.get_prev_point(points[4]) == points[1]
    assert sequence.get_nearest_prev_point(points[3]) == points[1]
    assert sequence.get_nearest_prev_point(points[4]) == points[1]
    assert sequence.get_next_point(points[3]) == points[4]
    assert sequence.get_next_point(points[2]) == points[4]
    assert sequence.get_next_point_on_sequence(points[3]) == points[4]
    assert sequence.get_next_point_on_sequence(points[6]) == points[8]

    sequence = IntegerSequence('R/P1!(1,3,4)', 1, 10)
    assert sequence.get_first_point(points[1]) == points[2]
    assert sequence.get_first_point(points[0]) == points[2]
    assert sequence.get_start_point() == points[2]

    sequence = IntegerSequence('R/P1!(8,9,10)', 1, 10)
    assert sequence.get_stop_point() == points[7]


def test_exclusions_extensive():
    """Test IntegerSequence methods for sequences with exclusions."""
    point_0 = IntegerPoint(0)
    point_1 = IntegerPoint(1)
    point_2 = IntegerPoint(2)
    point_3 = IntegerPoint(3)
    point_4 = IntegerPoint(4)

    sequence = IntegerSequence('R/P1!3', 1, 5)
    assert not sequence.is_on_sequence(point_3)
    assert not sequence.is_valid(point_3)
    assert sequence.get_prev_point(point_3) == point_2
    assert sequence.get_prev_point(point_4) == point_2
    assert sequence.get_nearest_prev_point(point_3) == point_2
    assert sequence.get_nearest_prev_point(point_3) == point_2
    assert sequence.get_next_point(point_3) == point_4
    assert sequence.get_next_point(point_2) == point_4
    assert sequence.get_next_point_on_sequence(point_3) == point_4
    assert sequence.get_next_point_on_sequence(point_2) == point_4

    sequence = IntegerSequence('R/P1!1', 1, 5)
    assert sequence.get_first_point(point_1) == point_2
    assert sequence.get_first_point(point_0) == point_2
    assert sequence.get_start_point() == point_2

    sequence = IntegerSequence('R/P1!5', 1, 5)
    assert sequence.get_stop_point() == point_4


def test_simple():
    """Run some simple tests for integer cycling."""
    sequence = IntegerSequence('R/1/P3', 1, 10)
    start = sequence.p_start
    stop = sequence.p_stop

    # Test point generation forwards.
    point = start
    output = []
    while point and stop and point <= stop:
        output.append(point)
        point = sequence.get_next_point(point)
    assert [int(out) for out in output] == [1, 4, 7, 10]

    # Test point generation backwards.
    point = stop
    output = []
    while point and start and point >= start:
        output.append(point)
        point = sequence.get_prev_point(point)
    assert [int(out) for out in output] == [10, 7, 4, 1]

    # Test sequence comparison
    sequence1 = IntegerSequence('R/1/P2', 1, 10)
    sequence2 = IntegerSequence('R/1/P2', 1, 10)
    assert sequence1 == sequence2
    sequence2.set_offset(IntegerInterval('-P2'))
    assert sequence1 == sequence2
    sequence2.set_offset(IntegerInterval('-P1'))
    assert sequence1 != sequence2


def test_interval_parsing_error():
    """It should reject invalid intervals."""
    with pytest.raises(IntervalParsingError):
        IntegerInterval(42)
    with pytest.raises(IntervalParsingError):
        IntegerInterval('forty two')


def test_sequence_parsing_error():
    with pytest.raises(SequenceParsingError):
        IntegerSequence('zz0+za', 1)


def test_interval_arithmetic():
    """It should do basic maths on integer intervals."""
    a = IntegerInterval('P2')
    b = IntegerInterval('P3')
    p = IntegerPoint('3')

    assert a + b == IntegerInterval('P5')
    assert a + p == IntegerPoint('5')
    assert a - b == IntegerInterval('-P1')
    assert a - p == IntegerPoint('-1')

    assert abs(IntegerInterval('-P2')) == IntegerInterval('P2')

    assert a + IntegerInterval.get_null_offset() == a

    with pytest.raises(CyclerTypeError):
        IntegerPoint(1000) - ISO8601Point('1000')

    with pytest.raises(CyclerTypeError):
        IntegerPoint(1000) + ISO8601Point('1000')

    with pytest.raises(CyclerTypeError):
        IntegerInterval('P1') - ISO8601Interval('P1Y')

    with pytest.raises(CyclerTypeError):
        IntegerInterval('P1') + ISO8601Interval('P1Y')


def test_async_expr():
    """The async expression should run once and only once."""
    point = IntegerPoint('5')
    sequence = IntegerSequence(IntegerSequence.get_async_expr(point), 1, 10)
    assert sequence.get_next_point(IntegerPoint('1')) == point
    assert sequence.get_next_point(IntegerPoint('5')) is None


def test_point_comparisons():
    # basic comparisons
    assert IntegerPoint(1) == IntegerPoint(1)
    assert IntegerPoint(1) < IntegerPoint(2)
    assert IntegerPoint(1) <= IntegerPoint(2)
    assert IntegerPoint(2) >= IntegerPoint(1)
    assert IntegerPoint(1) != IntegerPoint(2)
    assert IntegerInterval('P1') == IntegerInterval('P1')
    assert IntegerInterval('P1') < IntegerInterval('P2')
    assert IntegerInterval('P1') <= IntegerInterval('P2')
    assert IntegerInterval('P2') >= IntegerInterval('P1')
    assert IntegerInterval('P1') != IntegerInterval('P2')

    # None comparisons work counter intuatively
    # (reason unknown)
    assert IntegerPoint(1) < None
    assert None > IntegerPoint(1)
    assert IntegerInterval('P1') < None
    assert None > IntegerInterval('P1')

    # compare against other PointBase implementations
    assert ISO8601Point('1000') > IntegerPoint(1000)
    assert IntegerPoint(1000) < ISO8601Point('1000')
    assert ISO8601Interval('P1Y') > IntegerInterval('P1')
    assert IntegerInterval('P1') < ISO8601Interval('P1Y')


def test_string_representations():
    p = IntegerPoint(1)
    assert str(p) == '1'
    assert repr(p) == '1'

    i = IntegerInterval('P1')
    assert str(i) == 'P1'
    assert repr(i) == '<IntegerInterval P1>'

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

import unittest

from cylc.flow.cycling.integer import (
    IntegerSequence, IntegerPoint, IntegerInterval)


class TestIntegerSequence(unittest.TestCase):
    """Contains unit tests for the IntegerSequence class."""

    def test_exclusions_simple(self):
        """Test the generation of points for integer sequences with exclusions.
        """
        sequence = IntegerSequence('R/P1!3', 1, 5)
        output = []
        point = sequence.get_start_point()
        while point:
            output.append(point)
            point = sequence.get_next_point(point)
        self.assertEqual([int(out) for out in output], [1, 2, 4, 5])

    def test_multiple_exclusions_simple(self):
        """Tests the multiple exclusion syntax for integer notation"""
        sequence = IntegerSequence('R/P1!(2,3,7)', 1, 10)
        output = []
        point = sequence.get_start_point()
        while point:
            output.append(point)
            point = sequence.get_next_point(point)
        self.assertEqual([int(out) for out in output], [1, 4, 5, 6, 8, 9, 10])

    def test_multiple_exclusions_integer_sequence(self):
        """Tests the multiple exclusion syntax for integer notation"""
        sequence = IntegerSequence('P1 ! P2', 1, 10)
        output = []
        point = sequence.get_start_point()
        while point:
            output.append(point)
            point = sequence.get_next_point(point)
        self.assertEqual([int(out) for out in output], [2, 4, 6, 8, 10])

    def test_multiple_exclusions_integer_sequence2(self):
        """Tests the multiple exclusion syntax for integer notation"""
        sequence = IntegerSequence('P1 ! +P1/P2', 1, 10)
        output = []
        point = sequence.get_start_point()
        while point:
            output.append(point)
            point = sequence.get_next_point(point)
        self.assertEqual([int(out) for out in output], [1, 3, 5, 7, 9])

    def test_multiple_exclusions_integer_sequence3(self):
        """Tests the multiple exclusion syntax for integer notation"""
        sequence = IntegerSequence('P1 ! (P2, 6, 8) ', 1, 10)
        output = []
        point = sequence.get_start_point()
        while point:
            output.append(point)
            point = sequence.get_next_point(point)
        self.assertEqual([int(out) for out in output], [2, 4, 10])

    def test_multiple_exclusions_integer_sequence_weird_valid_formatting(self):
        """Tests the multiple exclusion syntax for integer notation"""
        sequence = IntegerSequence('P1 !(P2,     6,8) ', 1, 10)
        output = []
        point = sequence.get_start_point()
        while point:
            output.append(point)
            point = sequence.get_next_point(point)
        self.assertEqual([int(out) for out in output], [2, 4, 10])

    def test_multiple_exclusions_integer_sequence_invalid_formatting(self):
        """Tests the multiple exclusion syntax for integer notation"""
        sequence = 'P1 !(6,8), P2 '
        self.assertRaises(Exception, IntegerSequence, sequence, 1, 10)

    def test_multiple_exclusions_extensive(self):
        """Tests IntegerSequence methods for sequences with multi-exclusions"""
        points = [IntegerPoint(i) for i in range(10)]
        sequence = IntegerSequence('R/P1!(2,3,7)', 1, 10)
        self.assertFalse(sequence.is_on_sequence(points[3]))
        self.assertFalse(sequence.is_valid(points[3]))
        self.assertEqual(sequence.get_prev_point(points[3]), points[1])
        self.assertEqual(sequence.get_prev_point(points[4]), points[1])
        self.assertEqual(sequence.get_nearest_prev_point(points[3]), points[1])
        self.assertEqual(sequence.get_nearest_prev_point(points[4]), points[1])
        self.assertEqual(sequence.get_next_point(points[3]), points[4])
        self.assertEqual(sequence.get_next_point(points[2]), points[4])
        self.assertEqual(sequence.get_next_point_on_sequence(
            points[3]),
            points[4])
        self.assertEqual(sequence.get_next_point_on_sequence(
            points[6]),
            points[8])

        sequence = IntegerSequence('R/P1!(1,3,4)', 1, 10)
        self.assertEqual(sequence.get_first_point(points[1]), points[2])
        self.assertEqual(sequence.get_first_point(points[0]), points[2])
        self.assertEqual(sequence.get_start_point(), points[2])

        sequence = IntegerSequence('R/P1!(8,9,10)', 1, 10)
        self.assertEqual(sequence.get_stop_point(), points[7])

    def test_exclusions_extensive(self):
        """Test IntegerSequence methods for sequences with exclusions."""
        point_0 = IntegerPoint(0)
        point_1 = IntegerPoint(1)
        point_2 = IntegerPoint(2)
        point_3 = IntegerPoint(3)
        point_4 = IntegerPoint(4)

        sequence = IntegerSequence('R/P1!3', 1, 5)
        self.assertFalse(sequence.is_on_sequence(point_3))
        self.assertFalse(sequence.is_valid(point_3))
        self.assertEqual(sequence.get_prev_point(point_3), point_2)
        self.assertEqual(sequence.get_prev_point(point_4), point_2)
        self.assertEqual(sequence.get_nearest_prev_point(point_3), point_2)
        self.assertEqual(sequence.get_nearest_prev_point(point_3), point_2)
        self.assertEqual(sequence.get_next_point(point_3), point_4)
        self.assertEqual(sequence.get_next_point(point_2), point_4)
        self.assertEqual(sequence.get_next_point_on_sequence(point_3), point_4)
        self.assertEqual(sequence.get_next_point_on_sequence(point_2), point_4)

        sequence = IntegerSequence('R/P1!1', 1, 5)
        self.assertEqual(sequence.get_first_point(point_1), point_2)
        self.assertEqual(sequence.get_first_point(point_0), point_2)
        self.assertEqual(sequence.get_start_point(), point_2)

        sequence = IntegerSequence('R/P1!5', 1, 5)
        self.assertEqual(sequence.get_stop_point(), point_4)

    def test_simple(self):
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
        self.assertEqual([int(out) for out in output], [1, 4, 7, 10])

        # Test point generation backwards.
        point = stop
        output = []
        while point and start and point >= start:
            output.append(point)
            point = sequence.get_prev_point(point)
        self.assertEqual([int(out) for out in output], [10, 7, 4, 1])

        # Test sequence comparison
        sequence1 = IntegerSequence('R/1/P2', 1, 10)
        sequence2 = IntegerSequence('R/1/P2', 1, 10)
        self.assertEqual(sequence1, sequence2)
        sequence2.set_offset(IntegerInterval('-P2'))
        self.assertEqual(sequence1, sequence2)
        sequence2.set_offset(IntegerInterval('-P1'))
        self.assertNotEqual(sequence1, sequence2)


if __name__ == '__main__':
    unittest.main()

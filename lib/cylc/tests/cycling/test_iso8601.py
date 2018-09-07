#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

from cylc.cycling.iso8601 import init, ISO8601Sequence, ISO8601Point, ISO8601Interval


class TestISO8601Sequence(unittest.TestCase):
    """Contains unit tests for the ISO8601Sequence class."""

    def test_exclusions_simple(self):
        """Test the generation of points for sequences with exclusions."""
        init(time_zone='Z')
        sequence = ISO8601Sequence('PT1H!20000101T02Z', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        while point and count < 4:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        self.assertEqual(output, ['20000101T0000Z', '20000101T0100Z',
                                  '20000101T0300Z', '20000101T0400Z'])

    def test_exclusions_offset(self):
        """Test the generation of points for sequences with exclusions
        that have an offset on the end"""
        init(time_zone='Z')
        sequence = ISO8601Sequence('PT1H!20000101T00Z+PT1H', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        while point and count < 4:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        self.assertEqual(output, ['20000101T0000Z', '20000101T0200Z',
                                  '20000101T0300Z', '20000101T0400Z'])

    def test_multiple_exclusions_complex1(self):
        """Tests sequences that have multiple exclusions and a more
        complicated format"""

        # A sequence that specifies a dep start time
        sequence = ISO8601Sequence('20000101T01Z/PT1H!20000101T02Z',
                                   '20000101T01Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make four sequence points
        while point and count < 4:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect one of the hours to be excluded: T02
        self.assertEqual(output, ['20000101T0100Z', '20000101T0300Z',
                                  '20000101T0400Z', '20000101T0500Z'])

    def test_multiple_exclusions_complex2(self):
        """Tests sequences that have multiple exclusions and a more
        complicated format"""

        # A sequence that specifies a dep start time
        sequence = ISO8601Sequence('20000101T01Z/PT1H!'
                                   '(20000101T02Z,20000101T03Z)',
                                   '20000101T00Z',
                                   '20000101T05Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make four sequence points
        while point and count < 3:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect two of the hours to be excluded: T02, T03
        self.assertEqual(output, ['20000101T0100Z', '20000101T0400Z',
                                  '20000101T0500Z'])

    def test_multiple_exclusions_simple(self):
        """Tests generation of points for sequences with multiple exclusions
        """
        init(time_zone='Z')
        sequence = ISO8601Sequence('PT1H!(20000101T02Z,20000101T03Z)',
                                   '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make four sequence points
        while point and count < 4:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect two of the hours to be excluded: T02 and T03
        self.assertEqual(output, ['20000101T0000Z', '20000101T0100Z',
                                  '20000101T0400Z', '20000101T0500Z'])

    def test_advanced_exclusions_partial_datetime1(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run 3-hourly but not at 06:00 (from the ICP)
        sequence = ISO8601Sequence('PT3H!T06', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make ten sequence points
        while point and count < 10:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect every T06 to be excluded
        self.assertEqual(output, ['20000101T0000Z', '20000101T0300Z',
                                  '20000101T0900Z', '20000101T1200Z',
                                  '20000101T1500Z', '20000101T1800Z',
                                  '20000101T2100Z', '20000102T0000Z',
                                  '20000102T0300Z', '20000102T0900Z'])

    def test_advanced_exclusions_partial_datetime2(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run hourly but not at 00:00, 06:00, 12:00, 18:00
        sequence = ISO8601Sequence('T-00!(T00, T06, T12, T18)', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make 18 sequence points
        while point and count < 18:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect T00, T06, T12, and T18 to be excluded
        self.assertEqual(output, ['20000101T0100Z', '20000101T0200Z',
                                  '20000101T0300Z', '20000101T0400Z',
                                  '20000101T0500Z', '20000101T0700Z',
                                  '20000101T0800Z', '20000101T0900Z',
                                  '20000101T1000Z', '20000101T1100Z',
                                  '20000101T1300Z', '20000101T1400Z',
                                  '20000101T1500Z', '20000101T1600Z',
                                  '20000101T1700Z', '20000101T1900Z',
                                  '20000101T2000Z', '20000101T2100Z'])

    def test_advanced_exclusions_partial_datetime3(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run 5 minutely but not at 15 minutes past the hour from ICP
        sequence = ISO8601Sequence('PT5M!T-15', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make 15 sequence points
        while point and count < 15:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect xx:15 (15 minutes past the hour) to be excluded
        self.assertEqual(output, ['20000101T0000Z', '20000101T0005Z',
                                  '20000101T0010Z',
                                  '20000101T0020Z', '20000101T0025Z',
                                  '20000101T0030Z', '20000101T0035Z',
                                  '20000101T0040Z', '20000101T0045Z',
                                  '20000101T0050Z', '20000101T0055Z',
                                  '20000101T0100Z', '20000101T0105Z',
                                  '20000101T0110Z', '20000101T0120Z'])

    def test_advanced_exclusions_partial_datetime4(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run daily at 00:00 except on Mondays
        sequence = ISO8601Sequence('T00!W-1T00', '20170422T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make 19 sequence points
        while point and count < 9:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect Monday 24th April and Monday 1st May
        # to be excluded.
        self.assertEqual(output, ['20170422T0000Z', '20170423T0000Z',
                                  '20170425T0000Z', '20170426T0000Z',
                                  '20170427T0000Z', '20170428T0000Z',
                                  '20170429T0000Z', '20170430T0000Z',
                                  '20170502T0000Z'])

    def test_exclusions_to_string(self):
        init(time_zone='Z')
        # Chack that exclusions are not included where they should not be.
        basic = ISO8601Sequence('PT1H', '2000', '2001')
        self.assertFalse('!' in str(basic))

        # Check that exclusions are parsable.
        sequence = ISO8601Sequence('PT1H!(20000101T10Z, PT6H)', '2000', '2001')
        sequence2 = ISO8601Sequence(str(sequence), '2000', '2001')
        self.assertEqual(sequence, sequence2)

    def test_advanced_exclusions_sequences1(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run hourly from the ICP but not 3-hourly
        sequence = ISO8601Sequence('PT1H!PT3H', '20000101T01Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect to see hourly from ICP but not 3 hourly
        self.assertEqual(output, ['20000101T0200Z', '20000101T0300Z',
                                  '20000101T0500Z', '20000101T0600Z',
                                  '20000101T0800Z', '20000101T0900Z'])

    def test_advanced_exclusions_sequences2(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run hourly on the hour but not 3 hourly on the hour
        sequence = ISO8601Sequence('T-00!T-00/PT3H', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0100Z', '20000101T0200Z',
                                  '20000101T0400Z', '20000101T0500Z',
                                  '20000101T0700Z', '20000101T0800Z'])

    def test_advanced_exclusions_sequences3(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run daily at 12:00 except every 3rd day
        sequence = ISO8601Sequence('T12!P3D', '20000101T12Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000102T1200Z', '20000103T1200Z',
                                  '20000105T1200Z', '20000106T1200Z',
                                  '20000108T1200Z', '20000109T1200Z'])

    def test_advanced_exclusions_sequences4(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour.
        sequence = ISO8601Sequence('T01/PT1H!+PT3H/PT3H', '20000101T01Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0100Z', '20000101T0200Z',
                                  '20000101T0300Z', '20000101T0500Z',
                                  '20000101T0600Z', '20000101T0800Z'])

    def test_advanced_exclusions_sequences5(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour.
        sequence = ISO8601Sequence('T-00 ! 2000', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0100Z', '20000101T0200Z',
                                  '20000101T0300Z', '20000101T0400Z',
                                  '20000101T0500Z', '20000101T0600Z'])

    def test_advanced_exclusions_sequences_mix_points_sequences(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour.
        sequence = ISO8601Sequence('T-00 ! (2000, PT2H)', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0100Z', '20000101T0300Z',
                                  '20000101T0500Z', '20000101T0700Z',
                                  '20000101T0900Z', '20000101T1100Z'])

    def test_advanced_exclusions_sequences_implied_start_point(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour.
        sequence = ISO8601Sequence('T05/PT1H!PT3H', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0600Z', '20000101T0700Z',
                                  '20000101T0900Z', '20000101T1000Z',
                                  '20000101T1200Z', '20000101T1300Z'])

    def test_exclusions_sequences_points(self):
        """Test ISO8601Sequence methods for sequences with exclusions"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour
        sequence = ISO8601Sequence('T01/PT1H!PT3H', '20000101T01Z')

        point_0 = ISO8601Point('20000101T00Z')
        point_1 = ISO8601Point('20000101T01Z')
        point_2 = ISO8601Point('20000101T02Z')
        point_3 = ISO8601Point('20000101T03Z')
        point_4 = ISO8601Point('20000101T04Z')

        self.assertFalse(point_0 in sequence.exclusions)
        self.assertTrue(point_1 in sequence.exclusions)
        self.assertTrue(sequence.is_on_sequence(point_2))
        self.assertTrue(sequence.is_on_sequence(point_3))
        self.assertFalse(sequence.is_on_sequence(point_4))
        self.assertTrue(point_4 in sequence.exclusions)

    def test_exclusions_extensive(self):
        """Test ISO8601Sequence methods for sequences with exclusions"""
        init(time_zone='+05')
        sequence = ISO8601Sequence('PT1H!20000101T02+05', '20000101T00',
                                   '20000101T05')

        point_0 = ISO8601Point('20000101T0000+05')
        point_1 = ISO8601Point('20000101T0100+05')
        point_2 = ISO8601Point('20000101T0200+05')  # The excluded point.
        point_3 = ISO8601Point('20000101T0300+05')

        self.assertFalse(sequence.is_on_sequence(point_2))
        self.assertFalse(sequence.is_valid(point_2))
        self.assertEqual(sequence.get_prev_point(point_2), point_1)
        self.assertEqual(sequence.get_prev_point(point_3), point_1)
        self.assertEqual(sequence.get_prev_point(point_2), point_1)
        self.assertEqual(sequence.get_nearest_prev_point(point_3), point_1)
        self.assertEqual(sequence.get_next_point(point_1), point_3)
        self.assertEqual(sequence.get_next_point(point_2), point_3)

        sequence = ISO8601Sequence('PT1H!20000101T00+05', '20000101T00+05')
        self.assertEqual(sequence.get_first_point(point_0), point_1)
        self.assertEqual(sequence.get_start_point(), point_1)

    def test_multiple_exclusions_extensive(self):
        """Test ISO8601Sequence methods for sequences with multiple exclusions
        """
        init(time_zone='+05')
        sequence = ISO8601Sequence('PT1H!(20000101T02,20000101T03)',
                                   '20000101T00',
                                   '20000101T06')

        point_0 = ISO8601Point('20000101T0000+05')
        point_1 = ISO8601Point('20000101T0100+05')
        point_2 = ISO8601Point('20000101T0200+05')  # First excluded point
        point_3 = ISO8601Point('20000101T0300+05')  # Second excluded point
        point_4 = ISO8601Point('20000101T0400+05')

        # Check the excluded points are not on the sequence
        self.assertFalse(sequence.is_on_sequence(point_2))
        self.assertFalse(sequence.is_on_sequence(point_3))
        self.assertFalse(sequence.is_valid(point_2))  # Should be excluded
        self.assertFalse(sequence.is_valid(point_3))  # Should be excluded
        # Check that we can correctly retrieve previous points
        self.assertEqual(sequence.get_prev_point(point_2), point_1)
        # Should skip two excluded points
        self.assertEqual(sequence.get_prev_point(point_4), point_1)
        self.assertEqual(sequence.get_prev_point(point_2), point_1)
        self.assertEqual(sequence.get_nearest_prev_point(point_4), point_1)
        self.assertEqual(sequence.get_next_point(point_1), point_4)
        self.assertEqual(sequence.get_next_point(point_3), point_4)

        sequence = ISO8601Sequence('PT1H!20000101T00+05', '20000101T00')
        # Check that the first point is after 00.
        self.assertEqual(sequence.get_first_point(point_0), point_1)
        self.assertEqual(sequence.get_start_point(), point_1)

        # Check a longer list of exclusions
        # Also note you can change the format of the exclusion list
        # (removing the parentheses)
        sequence = ISO8601Sequence('PT1H!(20000101T02+05, 20000101T03+05,'
                                   '20000101T04+05)',
                                   '20000101T00',
                                   '20000101T06')
        self.assertEqual(sequence.get_prev_point(point_3), point_1)
        self.assertEqual(sequence.get_prev_point(point_4), point_1)

    def test_simple(self):
        """Run some simple tests for date-time cycling."""
        init(time_zone='Z')
        p_start = ISO8601Point('20100808T00')
        p_stop = ISO8601Point('20100808T02')
        i = ISO8601Interval('PT6H')
        self.assertEqual(p_start - i, ISO8601Point('20100807T18'))
        self.assertEqual(p_stop + i, ISO8601Point('20100808T08'))

        sequence = ISO8601Sequence('PT10M', str(p_start), str(p_stop), )
        sequence.set_offset(- ISO8601Interval('PT10M'))
        point = sequence.get_next_point(ISO8601Point('20100808T0000'))
        self.assertEqual(point, ISO8601Point('20100808T0010'))
        output = []

        # Test point generation forwards.
        while point and point < p_stop:
            output.append(point)
            self.assertTrue(sequence.is_on_sequence(point))
            point = sequence.get_next_point(point)
        self.assertEqual([str(out) for out in output],
                         ['20100808T0010Z', '20100808T0020Z',
                          '20100808T0030Z', '20100808T0040Z',
                          '20100808T0050Z', '20100808T0100Z',
                          '20100808T0110Z', '20100808T0120Z',
                          '20100808T0130Z', '20100808T0140Z',
                          '20100808T0150Z'])

        self.assertEqual(point, ISO8601Point('20100808T0200'))

        # Test point generation backwards.
        output = []
        while point and point >= p_start:
            output.append(point)
            self.assertTrue(sequence.is_on_sequence(point))
            point = sequence.get_prev_point(point)
        self.assertEqual([str(out) for out in output],
                         ['20100808T0200Z', '20100808T0150Z',
                          '20100808T0140Z', '20100808T0130Z',
                          '20100808T0120Z', '20100808T0110Z',
                          '20100808T0100Z', '20100808T0050Z',
                          '20100808T0040Z', '20100808T0030Z',
                          '20100808T0020Z', '20100808T0010Z',
                          '20100808T0000Z'])

        self.assertFalse(
            sequence.is_on_sequence(ISO8601Point('20100809T0005')))


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (C) 2013-2019 British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------------
"""Test isodatetime.datetimeoper functionalities."""


import os
import unittest
from unittest.mock import patch


from isodatetime.data import (
    get_timepoint_from_seconds_since_unix_epoch as seconds2point)
import isodatetime.datetimeoper


class TestDateTimeOperator(unittest.TestCase):
    """Test isodatetime.datetimeoper.TestDateTimeOperator functionalities."""

    @patch('isodatetime.datetimeoper.get_timepoint_for_now')
    def test_process_time_point_str_now_0(self, mock_now_func):
        """DateTimeOperator.process_time_point_str()"""
        # 2009-02-13T23:31:30Z
        mock_now = seconds2point(1234567890)
        mock_now_func.return_value = mock_now
        datetimeoper = isodatetime.datetimeoper.DateTimeOperator()
        self.assertEqual(str(mock_now), datetimeoper.process_time_point_str())
        self.assertEqual(
            str(mock_now),
            datetimeoper.process_time_point_str(datetimeoper.STR_NOW))

    @patch('isodatetime.datetimeoper.get_timepoint_for_now')
    def test_process_time_point_str_ref_0(self, mock_now_func):
        """DateTimeOperator.process_time_point_str('ref')

        But without explicit reference time, so default to now.
        """
        # 2009-02-13T23:31:30Z
        mock_now = seconds2point(1234567890)
        mock_now_func.return_value = mock_now
        datetimeoper = isodatetime.datetimeoper.DateTimeOperator()
        # Ensure that the ISODATETIMEREF environment variable is not set
        # Or the test may not work.
        environ = os.environ.copy()
        if datetimeoper.ENV_REF in environ:
            del environ[datetimeoper.ENV_REF]
        with patch.dict(os.environ, environ, clear=True):
            self.assertEqual(
                str(mock_now),
                datetimeoper.process_time_point_str(datetimeoper.STR_REF))

    def test_process_time_point_str_ref_1(self):
        """DateTimeOperator.process_time_point_str('ref')

        With explicit reference time.
        """
        # 2009-02-13T23:31:30Z
        ref_point_str = str(seconds2point(1234567890))
        datetimeoper = isodatetime.datetimeoper.DateTimeOperator(
            ref_point_str=ref_point_str)
        self.assertEqual(
            ref_point_str,
            datetimeoper.process_time_point_str(datetimeoper.STR_REF))

    def test_process_time_point_str_ref_2(self):
        """DateTimeOperator.process_time_point_str('ref')

        With explicit reference time as ISODATETIMEREF environment variable.
        """
        # 2009-02-13T23:31:30Z
        ref_point_str = str(seconds2point(1234567890))
        # Set ISODATETIMEREF.
        # Or the test may not work.
        environ = os.environ.copy()
        environ[isodatetime.datetimeoper.DateTimeOperator.ENV_REF] = (
            ref_point_str)
        with patch.dict(os.environ, environ):
            datetimeoper = isodatetime.datetimeoper.DateTimeOperator()
            self.assertEqual(
                ref_point_str,
                datetimeoper.process_time_point_str(datetimeoper.STR_REF))

    def test_process_time_point_str_x(self):
        """DateTimeOperator.process_time_point_str(...)

        Basic parse and dump of a time point string.
        """
        # 2009-02-13T23:31:30Z
        point_str = str(seconds2point(1234567890))
        datetimeoper = isodatetime.datetimeoper.DateTimeOperator()
        # Unix time
        self.assertEqual(
            '2019-01-11T10:40:15Z',
            datetimeoper.process_time_point_str(
                'Fri 11 Jan 10:40:15 UTC 2019',
                print_format=datetimeoper.CURRENT_TIME_DUMP_FORMAT_Z))
        # Basic
        self.assertEqual(
            point_str,
            datetimeoper.process_time_point_str(point_str))
        # +ve offset
        point_str_1 = str(seconds2point(1234567890 + 3600))
        self.assertEqual(
            point_str_1,
            datetimeoper.process_time_point_str(point_str, ['PT1H']))
        # +ve offset, time point like duration
        point_str_1 = str(seconds2point(1234567890 + 3600))
        self.assertEqual(
            point_str_1,
            datetimeoper.process_time_point_str(point_str, ['P0000-00-00T01']))
        # -ve offset
        point_str_2 = str(seconds2point(1234567890 - 86400))
        self.assertEqual(
            point_str_2,
            datetimeoper.process_time_point_str(point_str, ['-P1D']))
        # offsets that cancel out
        self.assertEqual(
            point_str,
            datetimeoper.process_time_point_str(point_str, ['PT1H', '-PT60M']))
        # Multiple offsets in 1 string
        point_str_3 = str(seconds2point(1234567890 - 86400 - 3600))
        self.assertEqual(
            point_str_3,
            datetimeoper.process_time_point_str(point_str, ['-P1DT1H']))
        # Multiple offsets
        self.assertEqual(
            point_str_3,
            datetimeoper.process_time_point_str(point_str, ['-P1D', '-PT1H']))
        # Bad time point string
        self.assertRaises(
            ValueError,
            datetimeoper.process_time_point_str, 'teatime')
        # Bad offset string
        with self.assertRaises(
            isodatetime.datetimeoper.OffsetValueError,
        ) as ctxmgr:
            datetimeoper.process_time_point_str(point_str, ['ages'])
        self.assertEqual('ages: bad offset value', str(ctxmgr.exception))
        # Bad offset string, unsupported time point like duration
        with self.assertRaises(
            isodatetime.datetimeoper.OffsetValueError,
        ) as ctxmgr:
            datetimeoper.process_time_point_str(point_str, ['P0000-W01-1'])
        self.assertEqual(
            'P0000-W01-1: bad offset value',
            str(ctxmgr.exception))

    def test_process_time_point_str_calendar(self):
        """DateTimeOperator.process_time_point_str(...)

        Alternate calendars.
        """
        self.assertEqual(
            'gregorian',
            isodatetime.datetimeoper.DateTimeOperator.get_calendar_mode())
        self.assertRaises(
            KeyError,
            isodatetime.datetimeoper.DateTimeOperator.set_calendar_mode,
            'milkywaygalactic')
        for cal, str_in, offsets, str_out in [
            # 360day
            ('360day', '20130301', ['-P1D'], '20130230'),
            ('360day', '20130230', ['P1D'], '20130301'),
            # 365day
            ('365day', '20130301', ['-P1D'], '20130228'),
            ('365day', '20130228', ['P1D'], '20130301'),
            # 366day
            ('366day', '20130301', ['-P1D'], '20130229'),
            ('366day', '20130229', ['P1D'], '20130301'),
        ]:
            # Calendar mode, is unfortunately, a global variable,
            # so needs to reset value on return.
            calendar_mode = (
                isodatetime.datetimeoper.DateTimeOperator.get_calendar_mode())
            # Calendar mode by constructor.
            try:
                datetimeoper = isodatetime.datetimeoper.DateTimeOperator(
                    calendar_mode=cal)
                self.assertEqual(
                    str_out,
                    datetimeoper.process_time_point_str(str_in, offsets))
            finally:
                isodatetime.datetimeoper.DateTimeOperator.set_calendar_mode(
                    calendar_mode)
            # Calendar mode by environment variable
            try:
                environ = os.environ.copy()
                key = (
                    isodatetime.datetimeoper.DateTimeOperator.ENV_CALENDAR_MODE
                )
                environ[key] = cal
                with patch.dict(os.environ, environ, clear=True):
                    datetimeoper = isodatetime.datetimeoper.DateTimeOperator()
                    self.assertEqual(
                        str_out,
                        datetimeoper.process_time_point_str(
                            str_in, offsets))
            finally:
                isodatetime.datetimeoper.DateTimeOperator.set_calendar_mode(
                    calendar_mode)

    def test_process_time_point_str_format(self):
        """DateTimeOperator.process_time_point_str(...)

        With parse_format and print_format.
        """
        for parse_format, print_format, point_str_in, point_str_out in [
            ('%d/%m/%Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S',
             '24/12/2012 06:00:00', '2012-12-24T06:00:00'),
            ('%Y,%M,%d,%H', '%Y%M%d%H', '2014,01,02,05', '2014010205'),
            ('%Y%m%d', '%y%m%d', '20141231', '141231'),
            ('%Y%m%d%H%M%S', '%s', '20140402100000', '1396432800'),
            ('%s', '%Y%m%dT%H%M%S%z', '1396429200', '20140402T090000+0000'),
            ('%d/%m/%Y %H:%M:%S', 'CCYY-MM-DDThh:mm',
             '24/12/2012 06:00:00', '2012-12-24T06:00'),
            (None, 'CCYY-MM-DDThh:mm+01:00',
             '2014-091T15:14:03Z', '2014-04-01T16:14+01:00'),
            (None, '%m', '2014-02-01T04:05:06', '02'),
            (None, '%Y', '2014-02-01T04:05:06', '2014'),
            (None, '%H', '2014-02-01T04:05:06', '04'),
            (None, '%Y%m%d_%H%M%S', '2014-02-01T04:05:06', '20140201_040506'),
            (None, '%Y.file', '2014-02-01T04:05:06', '2014.file'),
            (None, 'y%Ym%md%d', '2014-02-01T04:05:06', 'y2014m02d01'),
            (None, '%F', '2014-02-01T04:05:06', '2014-02-01'),

        ]:
            datetimeoper = isodatetime.datetimeoper.DateTimeOperator(
                utc_mode=True,
                parse_format=parse_format)
            self.assertEqual(
                point_str_out,
                datetimeoper.process_time_point_str(
                    point_str_in, print_format=print_format))
        # Bad parse format
        datetimeoper = isodatetime.datetimeoper.DateTimeOperator(
            parse_format='%o')
        with self.assertRaises(ValueError) as ctxmgr:
            datetimeoper.process_time_point_str('0000')
        self.assertEqual(
            "'o' is a bad directive in format '%o'",
            str(ctxmgr.exception))

    def test_format_duration_str_x(self):
        """DateTimeOperator.format_duration_str(...)"""
        datetimeoper = isodatetime.datetimeoper.DateTimeOperator()
        # Good ones
        for print_format, duration_str_in, duration_out in [
            ('s', 'PT1M', 60.0),
            ('s', 'P1DT1H1M1S', 90061.0),
            ('m', 'PT1S', 0.0166666666667),
            ('h', 'P832DT23H12M45S', 19991.2125),
            ('S', '-PT1M1S', -61.0),
        ]:
            self.assertAlmostEqual(
                duration_out,
                datetimeoper.format_duration_str(
                    duration_str_in, print_format))
        # Bad ones
        for print_format, duration_str_in in [
            ('y', 'PT1M'),
            ('s', 'quickquick'),
        ]:
            self.assertRaises(
                ValueError,
                datetimeoper.format_duration_str,
                duration_str_in, print_format)

    def test_diff_time_point_strs(self):
        """DateTimeOperator.diff_time_point_strs(...)"""
        datetimeoper = isodatetime.datetimeoper.DateTimeOperator(
            ref_point_str='20150106')
        for (
            time_point_str1,
            time_point_str2,
            offsets1, offsets2,
            print_format,
            duration_print_format,
            duration_out,
        ) in [
            (   # Positive
                '20130101T12',
                '20130301',
                None,
                None,
                None,
                None,
                'P58DT12H',
            ),
            (   # Positive, non integer seconds
                # Use (3.1 - 3.0) to bypass str(float) precision issue
                '20190101T010203',
                '20190101T010203.1',
                None,
                None,
                None,
                None,
                'PT%sS' % (str(3.1 - 3.0).replace('.', ',')),
            ),
            (   # Positive, non integer seconds, print format
                # Use (3.1 - 3.0) to bypass str(float) precision issue
                '20190101T010203',
                '20190101T010203.1',
                None,
                None,
                's',
                None,
                str(3.1 - 3.0),
            ),
            (   # Offset 1, reference time 2, positive
                '20140101',
                'ref',
                ['P11M24D'],
                None,
                None,
                None,
                'P12D',
            ),
            (   # Offset 2, positive
                '20100101T00',
                '20100201T00',
                None,
                ['P1D'],
                None,
                None,
                'P32D',
            ),
            (   # Neutral
                '20151225T00',
                '20151225',
                None,
                None,
                None,
                None,
                'P0Y',
            ),
            (   # Negative
                '20150101T12',
                '20130301',
                None,
                None,
                None,
                None,
                '-P671DT12H',
            ),
            (   # Alternate format
                '20130101T12',
                '20130301',
                None,
                None,
                'y,m,d,h,M,s',
                None,
                '0,0,58,12,0,0',
            ),
            (   # Offset 2, alternate format
                '0000',
                '0000',
                ['-PT2M'],
                None,
                'y,m,d,h,M,s',
                None,
                '0,0,0,0,2,0',
            ),
            (   # As seconds, positive
                '2000-01-01T00:00:00',
                '2000-01-01T01:00:00',
                None,
                None,
                None,
                's',
                3600.0,
            ),
            (   # As seconds, neutral
                '2000-01-01T00:00:00',
                '2000-01-01T00:00:00',
                None,
                None,
                None,
                's',
                0.0,
            ),
            (   # As seconds, negative
                '2000-01-01T00:00:00',
                '1999-12-31T23:00:00',
                None,
                None,
                None,
                's',
                -3600.0,
            ),
        ]:
            self.assertEqual(
                duration_out,
                datetimeoper.diff_time_point_strs(
                    time_point_str1,
                    time_point_str2,
                    offsets1,
                    offsets2,
                    print_format,
                    duration_print_format))


if __name__ == '__main__':
    unittest.main()

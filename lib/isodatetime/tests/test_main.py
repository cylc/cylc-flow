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
"""Test isodatetime.main."""


import os
import sys
import unittest
from unittest.mock import patch


import isodatetime
import isodatetime.main


class TestMain(unittest.TestCase):
    """Test isodatetime.main.main."""

    @patch('builtins.print')
    def test_1_version(self, mock_print):
        """Test print version."""
        argv = sys.argv
        for args in [['--version'], ['-V']]:
            sys.argv = [''] + args
            try:
                isodatetime.main.main()
                mock_print.assert_called_with(isodatetime.__version__)
            finally:
                sys.argv = argv

    @patch('builtins.print')
    def test_1_null(self, mock_print):
        """Test calling usage 1, no or now argument."""
        argv = sys.argv
        with patch.object(
            isodatetime.main.DateTimeOperator,
            'process_time_point_str',
            return_value='20190101T1234Z'
        ):
            for args in [[''], ['now']]:
                sys.argv = args
                try:
                    isodatetime.main.main()
                    mock_print.assert_called_with('20190101T1234Z')
                finally:
                    sys.argv = argv

    @patch('builtins.print')
    def test_1_good(self, mock_print):
        """Test calling usage 1, sample good arguments."""
        env_ref = isodatetime.main.DateTimeOperator.ENV_REF
        ref = os.environ.get(env_ref)
        argv = sys.argv
        for args, out in [
            (['20200101T00Z'], '20200101T00Z'),
            (['ref'], '20201225T0000Z'),
            # UTC mode
            (['-u', '20200101T00+0100'], '20191231T23+0000'),
            (['--utc', '20200101T00+0100'], '20191231T23+0000'),
            # With offsets
            (['-s', 'P1D', '20191231T00Z'], '20200101T00Z'),
            (['-s', 'P1D', '--offset=PT1H', '20191231T00Z'], '20200101T01Z'),
            # Print format
            (['-f', 'CCYY', '20191231T00Z'], '2019'),
            (['--format', 'CCYY', '20191231T00Z'], '2019'),
            (['--print-format', 'CCYY', '20191231T00Z'], '2019'),
            (['20200101T00-1130', '-f', 'CCYYMMDDThhmm+0000'],
             '20200101T1130+0000'),
            # Parse format
            (['--parse-format=%d/%m/%Y', '-f', 'CCYY-MM-DD', '31/12/2019'],
             '2019-12-31'),
            (['-p', '%d/%m/%Y', '-f', 'CCYY-MM-DD', '31/12/2019'],
             '2019-12-31'),
        ]:
            sys.argv = [''] + args
            os.environ[env_ref] = '20201225T0000Z'
            try:
                isodatetime.main.main()
                mock_print.assert_called_with(out)
            finally:
                sys.argv = argv
                if ref is not None:
                    os.environ[env_ref] = ref
                else:
                    del os.environ[env_ref]

    @patch('builtins.print')
    def test_1_bad(self, mock_print):
        """Test calling usage 1, sample bad arguments."""
        argv = sys.argv
        for args, out in [
            # Bad time point string
            (['201abc'], 'Invalid ISO 8601 date representation: 201abc'),
            # Bad offset string
            (['-s', 'add-a-year', '2019'], 'add-a-year: bad offset value'),
        ]:
            mock_print.reset_mock()
            sys.argv = [''] + args
            try:
                with self.assertRaises(SystemExit) as ctxmgr:
                    isodatetime.main.main()
                mock_print.assert_not_called()
                self.assertEqual(out, str(ctxmgr.exception))
            finally:
                sys.argv = argv

    @patch('builtins.print')
    def test_2_good(self, mock_print):
        """Test calling usage 2, sample good arguments."""
        env_ref = isodatetime.main.DateTimeOperator.ENV_REF
        ref = os.environ.get(env_ref)
        argv = sys.argv
        for args, out in [
            # Same
            (['ref', 'ref'], 'P0Y'),
            (['20380119', '20380119'], 'P0Y'),
            # Positive duration
            (['20181225', '20191225'], 'P365D'),
            (['-1', 'PT12H', '-2', 'PT12H', '20181225', '20191225'], 'P365D'),
            # Negative duration
            (['20191225', '20181225'], '-P365D'),
            (['--offset1=-PT6H', '--offset2=-PT6H', '20191225', '20181225'],
             '-P365D'),
        ]:
            sys.argv = [''] + args
            os.environ[env_ref] = '20201225T0000Z'
            try:
                isodatetime.main.main()
                mock_print.assert_called_with(out)
            finally:
                sys.argv = argv
                if ref is not None:
                    os.environ[env_ref] = ref
                else:
                    del os.environ[env_ref]

    @patch('builtins.print')
    def test_2_bad(self, mock_print):
        """Test calling usage 2, sample bad arguments."""
        argv = sys.argv
        for args, out in [
            # Bad time point string
            (['201abc', '2020'],
             'Invalid ISO 8601 date representation: 201abc'),
            # Bad offset string
            (['-1', 'add-a-year', '2018', '2019'],
             'add-a-year: bad offset value'),
        ]:
            mock_print.reset_mock()
            sys.argv = [''] + args
            try:
                with self.assertRaises(SystemExit) as ctxmgr:
                    isodatetime.main.main()
                mock_print.assert_not_called()
                self.assertEqual(out, str(ctxmgr.exception))
            finally:
                sys.argv = argv

    @patch('builtins.print')
    def test_3_good(self, mock_print):
        """Test calling usage 3, sample good arguments."""
        argv = sys.argv
        for args, out in [
            # Same
            (['--as-total=s', 'PT1H30M'], 5400),
            (['--as-total=s', 'P1D'], 86400),
            (['--as-total=h', 'P1D'], 24),
        ]:
            sys.argv = [''] + args
            try:
                isodatetime.main.main()
                mock_print.assert_called_with(out)
            finally:
                sys.argv = argv

    @patch('builtins.print')
    def test_3_bad(self, mock_print):
        """Test calling usage 3, sample bad arguments."""
        argv = sys.argv
        mock_print.reset_mock()
        sys.argv = ['', '--as-total=s', 'PS4']
        try:
            with self.assertRaises(SystemExit) as ctxmgr:
                isodatetime.main.main()
            mock_print.assert_not_called()
            self.assertEqual(
                'Invalid ISO 8601 duration representation: PS4',
                str(ctxmgr.exception))
        finally:
            sys.argv = argv

    @patch('builtins.print')
    def test_4_good(self, mock_print):
        """Test calling usage 4, sample good arguments."""
        argv = sys.argv
        for args, out in [
            # Forward
            (['-u', 'R/2020/P1Y'],
             '\n'.join('%d-01-01T00:00:00Z' % i for i in range(2020, 2030))),
            (['-u', 'R3/2020/P1Y'],
             '\n'.join('%d-01-01T00:00:00Z' % i for i in range(2020, 2023))),
            (['-u', '--max=5', 'R/2020/P1Y'],
             '\n'.join('%d-01-01T00:00:00Z' % i for i in range(2020, 2025))),
            (['-u', '--max=15', 'R/2020/P1Y'],
             '\n'.join('%d-01-01T00:00:00Z' % i for i in range(2020, 2035))),
            (['--print-format=%Y', 'R/2020/P1Y'],
             '\n'.join('%d' % i for i in range(2020, 2030))),
            # Reverse
            (['-u', 'R/P1Y/2020'],
             '\n'.join('%d-01-01T00:00:00Z' % i
                       for i in range(2020, 2010, -1))),
        ]:
            sys.argv = [''] + args
            try:
                isodatetime.main.main()
                mock_print.assert_called_with(out)
            finally:
                sys.argv = argv

    @patch('builtins.print')
    def test_4_bad(self, mock_print):
        """Test calling usage 4, sample bad arguments."""
        argv = sys.argv
        mock_print.reset_mock()
        sys.argv = ['', 'R/2020/2025']
        try:
            with self.assertRaises(SystemExit) as ctxmgr:
                isodatetime.main.main()
            mock_print.assert_not_called()
            self.assertEqual(
                'Invalid ISO 8601 recurrence representation: R/2020/2025',
                str(ctxmgr.exception))
        finally:
            sys.argv = argv


if __name__ == '__main__':
    unittest.main()

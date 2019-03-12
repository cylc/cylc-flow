#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import logging
import unittest

from cylc.config import check_varnames


GOOD_VARNAMES = ['aaa', 'BBB', 'C_a', '_']
GOOD_MULTI_VARNAMES = ['a,b,c', 'a, _', '_ , d']
BAD_VARNAMES = ['0a', '@f', 'f-g']
BAD_MULTI_VARNAMES = ['a,', ',b', 'a,03df, f', 'a, , b']


class TestConfig(unittest.TestCase):
    def test_check_varnames_good_singles(self):
        """Test that good variable names are accepted"""
        results = check_varnames(GOOD_VARNAMES)
        self.assertEqual(results, [])

    def test_check_varnames_good_multi(self):
        """Test that good multi-variable lines are accepted"""
        results = check_varnames(GOOD_MULTI_VARNAMES)
        self.assertEqual(results, [])

    def test_check_varnames_bad_varnames(self):
        """Test that bad variable names are caught"""
        results = check_varnames(BAD_VARNAMES)
        self.assertEqual(results, BAD_VARNAMES)

    def test_check_varnames_bad_multi(self):
        """Test that bad multi-variables lines are caught"""
        results = check_varnames(BAD_MULTI_VARNAMES)
        self.assertEqual(results, BAD_MULTI_VARNAMES)


if __name__ == '__main__':
    unittest.main()

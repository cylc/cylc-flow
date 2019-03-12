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

import unittest

from cylc.job_file import JobFileWriter


EXPECTED_READ = 'read -r %s <<< %s'

# List of multiple variable inputs
# input variables, input values, expected variables
MULTI = [("A,B", "$(echo test test)", "A B"),
         ("A, BC", "`echo test test`", "A BC")]

# List of single variable inputs
# input value, expected output value
SINGLES = [('~foo/bar bar', '~foo/"bar bar"'),
           ('~/bar bar', '~/"bar bar"'),
           ('~/a', '~/"a"'),
           ('test', '"test"'),
           ('~', '~'),
           ('~a', '~a')]


class TestJobFile(unittest.TestCase):
    def test_get_variable_value_definition(self):
        """Test the value for single variables are correctly quoted"""
        for in_value, out_value in SINGLES:
            res = JobFileWriter._get_variable_value_definition(in_value)
            self.assertEqual(out_value, res)

    def test_get_multi_variable_command(self):
        """Test that the multi-variables values are returned correctly"""
        for variable, value, expected_variable in MULTI:
            res = JobFileWriter._get_multi_variable_command(variable, value)
            self.assertEqual(EXPECTED_READ % (expected_variable, value),
                             res)


if __name__ == '__main__':
    unittest.main()

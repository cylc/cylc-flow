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
from tempfile import TemporaryFile
from unittest import mock

from cylc.flow.job_file import JobFileWriter

# List of tilde variable inputs
# input value, expected output value
TILDE_IN_OUT = [('~foo/bar bar', '~foo/"bar bar"'),
                ('~/bar bar', '~/"bar bar"'),
                ('~/a', '~/"a"'),
                ('test', '"test"'),
                ('~', '~'),
                ('~a', '~a')]


class TestJobFile(unittest.TestCase):
    def test_get_variable_value_definition(self):
        """Test the value for single/tilde variables are correctly quoted"""
        for in_value, out_value in TILDE_IN_OUT:
            res = JobFileWriter._get_variable_value_definition(in_value)
            self.assertEqual(out_value, res)

    @mock.patch("cylc.flow.job_file.glbl_cfg")
    def test_write_prelude_invalid_cylc_command(self, mocked_glbl_cfg):
        job_conf = {
            "batch_system_name": "background",
            "host": "localhost",
            "owner": "me"
        }
        mocked = mock.MagicMock()
        mocked_glbl_cfg.return_value = mocked
        mocked.get_host_item.return_value = 'cylc-testing'
        with self.assertRaises(ValueError) as ex:
            with TemporaryFile(mode="w+") as handle:
                JobFileWriter()._write_prelude(handle, job_conf)
        self.assertIn("bad cylc executable", str(ex.exception))


if __name__ == '__main__':
    unittest.main()

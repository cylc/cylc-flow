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

from cylc.flow.parsec.exceptions import ParsecError


class TestParsec(unittest.TestCase):

    def test_parsec_error_msg(self):
        parsec_error = ParsecError()
        self.assertEqual('', str(parsec_error))
        parsec_error = ParsecError('foo')
        self.assertEqual('foo', str(parsec_error))

    def test_parsec_error_str(self):
        msg = 'Turbulence!'
        parsec_error = ParsecError(msg)
        self.assertEqual(msg, str(parsec_error))


if __name__ == '__main__':
    unittest.main()

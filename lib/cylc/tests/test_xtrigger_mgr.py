#!/usr/bin/env python2

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

from cylc.xtrigger_mgr import RE_STR_TMPL


class TestXtriggerManager(unittest.TestCase):

    def test_extract_templates(self):
        """Test escaped templates in xtrigger arg string.

        They should be left alone and passed into the function as string
        literals, not identified as template args.
        """
        self.assertEqual(
            RE_STR_TMPL.findall('%(cat)s, %(dog)s, %%(fish)s'),
            ['cat', 'dog']
        )


if __name__ == '__main__':
    unittest.main()

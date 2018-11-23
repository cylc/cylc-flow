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

import os
import unittest

from cylc.hostuserutil import get_host, is_remote_host, is_remote_user


class TestLocal(unittest.TestCase):
    """Test is_remote* behaves with local host and user."""

    def test_users(self):
        """is_remote_user with local users."""
        self.assertFalse(is_remote_user(None))
        self.assertFalse(is_remote_user(os.getenv('USER')))

    def test_hosts(self):
        """is_remote_host with local hosts."""
        self.assertFalse(is_remote_host(None))
        self.assertFalse(is_remote_host('localhost'))
        self.assertFalse(is_remote_host(os.getenv('HOSTNAME')))
        self.assertFalse(is_remote_host(get_host()))


if __name__ == '__main__':
    unittest.main()

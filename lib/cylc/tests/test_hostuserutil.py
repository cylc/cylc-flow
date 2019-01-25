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

import os
import unittest

from cylc.hostuserutil import (
    get_fqdn_by_host, get_host, get_user, get_user_home, is_remote_host,
    is_remote_user)


class TestHostUserUtil(unittest.TestCase):
    """Test aspects of "cylc.hostuserutil"."""

    def test_is_remote_user_on_current_user(self):
        """is_remote_user with current user."""
        self.assertFalse(is_remote_user(None))
        self.assertFalse(is_remote_user(os.getenv('USER')))

    def test_is_remote_host_on_localhost(self):
        """is_remote_host with localhost."""
        self.assertFalse(is_remote_host(None))
        self.assertFalse(is_remote_host('localhost'))
        self.assertFalse(is_remote_host(os.getenv('HOSTNAME')))
        self.assertFalse(is_remote_host(get_host()))

    def test_get_fqdn_by_host_on_bad_host(self):
        """get_fqdn_by_host bad host."""
        bad_host = 'nosuchhost.nosuchdomain.org'
        try:  # Future: Replace with assertRaises context manager syntax
            get_fqdn_by_host(bad_host)
        except IOError as exc:
            self.assertEqual(exc.filename, bad_host)
            self.assertEqual(
                "[Errno -2] Name or service not known: '%s'" % bad_host,
                str(exc))

    def test_get_user(self):
        """get_user."""
        self.assertEqual(os.getenv('USER'), get_user())

    def test_get_user_home(self):
        """get_user_home."""
        self.assertEqual(os.getenv('HOME'), get_user_home())


if __name__ == '__main__':
    unittest.main()

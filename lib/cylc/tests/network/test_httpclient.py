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

from cylc.hostuserutil import get_host
from cylc.network.httpclient import SuiteRuntimeServiceClient
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager)


class TestSuiteRuntimeServiceClient(unittest.TestCase):
    """Unit testing class to test the methods in SuiteRuntimeServiceClient
    """

    def test_url_compiler_https(self):
        """Tests that the url parser works for a single url and command
        using https"""
        myclient = SuiteRuntimeServiceClient(
            "test-suite", host=get_host(), port=80)
        myclient.comms1[SuiteSrvFilesManager.KEY_COMMS_PROTOCOL] = 'https'
        self.assertEqual(
            'https://%s:80/test_command?apples=False&oranges=True' %
            get_host(),
            myclient._call_server_get_url(
                "test_command", apples="False", oranges="True"))

    def test_compile_url_compiler_http(self):
        """Test that the url compiler produces a http request when
        http is specified."""
        myclient = SuiteRuntimeServiceClient(
            "test-suite", host=get_host(), port=80)
        myclient.comms1[SuiteSrvFilesManager.KEY_COMMS_PROTOCOL] = 'http'
        self.assertEqual(
            'http://%s:80/test_command?apples=False&oranges=True' %
            get_host(),
            myclient._call_server_get_url(
                "test_command", apples="False", oranges="True"))

    def test_compile_url_compiler_none_specified(self):
        """Test that the url compiler produces a http request when
        none is specified. This should retrieve it from the
        global config."""
        myclient = SuiteRuntimeServiceClient(
            "test-suite", host=get_host(), port=80)
        url = myclient._call_server_get_url(
            "test_command", apples="False", oranges="True")
        # Check that the url has had http (or https) appended
        # to it. (If it does not start with "http*" then something
        # has gone wrong.)
        self.assertTrue(url.startswith("http"))


if __name__ == '__main__':
    unittest.main()

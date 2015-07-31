#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
from cylc.network import PYRO_LOG_OBJ_NAME
from cylc.network.pyro_base import PyroClient, PyroServer
from cylc.network import check_access_priv


class SuiteLogServer(PyroServer):
    """Server-side suite log interface."""

    def __init__(self, log):
        super(SuiteLogServer, self).__init__()
        self.log = log
        self.err_file = log.get_err_path()

    def _get_err_has_changed(self, prev_err_size):
        """Return True if the file has changed size compared to prev_size."""
        return self._get_err_size() != prev_err_size

    def _get_err_size(self):
        """Return the os.path.getsize result for the error file."""

        try:
            size = os.path.getsize(self.err_file)
        except (IOError, OSError) as e:
            self.log.warning("Could not read suite err log file: %s" % e)
            return 0
        return size

    def get_err_content(self, prev_size=0, max_lines=100):
        """Return the content and new size of the error file."""

        check_access_priv(self, 'full-read')
        self.report("get_err_content")
        if not self._get_err_has_changed(prev_size):
            return [], prev_size
        try:
            f = open(self.err_file, "r")
            f.seek(prev_size)
            new_content = f.read()
            f.close()
            size = self._get_err_size()
        except (IOError, OSError) as e:
            self.log.warning("Could not read suite err log file: %s" % e)
            return "", prev_size
        new_content_lines = new_content.splitlines()[-max_lines:]
        return "\n".join(new_content_lines), size


class SuiteLogClient(PyroClient):
    """Client-side suite log interface."""

    target_server_object = PYRO_LOG_OBJ_NAME

    def get_err_content(self, *args):
        #return self.pyro_proxy.get_err_content(prev_size, max_lines)
        return self.call_server_func("get_err_content", *args)

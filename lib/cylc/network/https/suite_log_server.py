#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Server-side suite log interface."""

import cherrypy
import os

from cylc.network.https.base_server import BaseCommsServer
from cylc.network import check_access_priv


class SuiteLogServer(BaseCommsServer):
    """Server-side suite log interface."""

    def __init__(self, log):
        super(SuiteLogServer, self).__init__()
        self.log = log
        self.err_file = log.get_log_path(log.ERR)

    def _get_err_has_changed(self, prev_err_size):
        """Return True if the file has changed size compared to prev_size."""
        return self._get_err_size() != prev_err_size

    def _get_err_size(self):
        """Return the os.path.getsize result for the error file."""

        try:
            size = os.path.getsize(self.err_file)
        except (IOError, OSError) as exc:
            self._warn_read_err(exc)
            return 0
        return size

    def _warn_read_err(self, exc):
        """Issue warning on failure to read/stat the ERR log file."""
        my_log = self.log.get_log(self.log.LOG)
        if my_log is not None:
            my_log.warning("Could not read suite err log file: %s" % exc)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_err_content(self, prev_size, max_lines):
        """Return the content and new size of the error file."""
        check_access_priv(self, 'full-read')
        self.report("get_err_content")
        prev_size = int(prev_size)
        max_lines = int(max_lines)
        if not self._get_err_has_changed(prev_size):
            return [], prev_size
        try:
            handle = open(self.err_file, "r")
            handle.seek(prev_size)
            new_content = handle.read()
            handle.close()
            size = self._get_err_size()
        except (IOError, OSError) as exc:
            self._warn_read_err(exc)
            return "", prev_size
        new_content_lines = new_content.splitlines()[-max_lines:]
        return "\n".join(new_content_lines), size

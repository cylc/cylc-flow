#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
"""Base classes for HTTPS subsystem server."""

import cherrypy
import inspect

from cylc.network.https.client_reporter import CommsClientReporter


class BaseCommsServer(object):
    """Base class for server-side suite object interfaces."""

    def __init__(self):
        self.client_reporter = CommsClientReporter.get_inst()

    def signout(self):
        """Wrap client_reporter.signout."""
        self.client_reporter.signout(self)

    def report(self, command):
        """Wrap client_reporter.report."""
        self.client_reporter.report(command, self)

    @cherrypy.expose
    @cherrypy.tools.json_out()    
    def index(self):
        exposed_methods = inspect.getmembers(
            self, lambda _: inspect.ismethod(_) and hasattr(_, "exposed"))
        method_info = []
        for method, value in sorted(exposed_methods):
            doc = inspect.getdoc(value)
            argspec = inspect.getargspec(value)
            if "self" in argspec.args:
                argspec.args.remove("self")
            argdoc = inspect.formatargspec(*argspec)
            method_info.append({"name": method,
                                "argdoc": argdoc,
                                "doc": inspect.getdoc(value)})
        return method_info

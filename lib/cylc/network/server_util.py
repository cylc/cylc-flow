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

"""Server side utilities."""

import cherrypy
from uuid import uuid4


def get_client_info():
    """Return information about the most recent cherrypy request, if any."""
    auth_user = cherrypy.request.login
    info = cherrypy.request.headers
    origin_string = info.get("User-Agent", "")
    origin_props = {}
    if origin_string:
        try:
            origin_props = dict(
                [_.split("/", 1) for _ in origin_string.split()]
            )
        except ValueError:
            pass
    prog_name = origin_props.get("prog_name", "Unknown")
    uuid = origin_props.get("uuid", uuid4())
    if info.get("From") and "@" in info["From"]:
        user, host = info["From"].split("@")
    else:
        user, host = ("Unknown", "Unknown")
    return auth_user, prog_name, user, host, uuid

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

from cylc.network import COMMS_BCAST_OBJ_NAME
from cylc.network.https.base_client import BaseCommsClient


class BroadcastClient(BaseCommsClient):
    """Client-side suite broadcast interface."""

    def broadcast(self, cmd, **kwargs):
        if cmd == "get":
            return self.call_server_func(COMMS_BCAST_OBJ_NAME, cmd,
                                         method=self.METHOD_GET, **kwargs)
        if cmd == "expire":
            return self.call_server_func(COMMS_BCAST_OBJ_NAME, cmd, **kwargs)
        return self.call_server_func(
            COMMS_BCAST_OBJ_NAME, cmd, payload=kwargs)

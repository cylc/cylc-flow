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

# A minimal server/client pair to allow client programs to identify
# what suite is running at a given cylc port - by suite name and owner.

from cylc.network import COMMS_SUITEID_OBJ_NAME
from cylc.network.https.base_client import BaseCommsClient, BaseCommsClientAnon


class SuiteIdClient(BaseCommsClient):
    """Client-side suite identity interface."""

    METHOD = BaseCommsClient.METHOD_GET

    def identify(self):
        return self.call_server_func(COMMS_SUITEID_OBJ_NAME, "identify")


class SuiteIdClientAnon(BaseCommsClientAnon):
    """Client-side suite identity interface."""

    METHOD = BaseCommsClient.METHOD_GET

# TODO - think this can be removed now
#     def __init__(self, *args, **kwargs):
#         super(SuiteIdClientAnon, self).__init__(*args, **kwargs)

    def identify(self):
        return self.call_server_func(COMMS_SUITEID_OBJ_NAME, "identify")



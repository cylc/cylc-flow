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
"""HTTPS server-side identification interface."""

import cherrypy

from cylc.config import SuiteConfig
from cylc.network import (
    KEY_DESCRIPTION, KEY_GROUP, KEY_NAME, KEY_OWNER, KEY_STATES,
    KEY_TASKS_BY_STATE, KEY_TITLE, KEY_UPDATE_TIME)
from cylc.network.https.base_server import BaseCommsServer
from cylc.network.https.suite_state_server import StateSummaryServer
from cylc.network import access_priv_ok


class SuiteIdServer(BaseCommsServer):
    """Server-side identification interface."""

    _INSTANCE = None

    @classmethod
    def get_inst(cls, name=None, owner=None):
        """Return a singleton instance."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls(name, owner)
        return cls._INSTANCE

    def __init__(self, name, owner):
        self.owner = owner
        self.name = name
        super(SuiteIdServer, self).__init__()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def identify(self):
        self.report("identify")
        result = {}
        if access_priv_ok(self, "identity"):
            result[KEY_NAME] = self.name
            result[KEY_OWNER] = self.owner
        if access_priv_ok(self, "description"):
            config = SuiteConfig.get_inst()
            result[KEY_TITLE] = config.cfg['meta'][KEY_TITLE]
            result[KEY_DESCRIPTION] = config.cfg['meta'][KEY_DESCRIPTION]
            result[KEY_GROUP] = config.cfg[KEY_GROUP]
        if access_priv_ok(self, "state-totals"):
            summary_server = StateSummaryServer.get_inst()
            result[KEY_UPDATE_TIME] = summary_server.get_summary_update_time()
            result[KEY_STATES] = summary_server.get_state_totals()
            result[KEY_TASKS_BY_STATE] = summary_server.get_tasks_by_state()
        return result

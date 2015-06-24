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

# A minimal Pyro-connected object to allow client programs to identify
# what suite is running at a given cylc port - by suite name and owner.

# All *other* suite objects should be connected to Pyro via qualified
# names: owner.suite.object, to prevent accidental access to the wrong
# suite. This object, however, should be connected unqualified so that
# that same ID method can be called on any active cylc port.

import cylc.flags
from cylc.network.pyro_base import PyroServer
from cylc.network.suite_state import StateSummaryServer
from cylc.network import access_priv_ok
from cylc.config import SuiteConfig


class SuiteIdServer(PyroServer):
    """Server-side external trigger interface."""

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

    def identify(self):
        self.report("identify")
        result = {}
        if access_priv_ok(self, "identity"):
            result['name'] = self.name
            result['owner'] = self.owner
        if access_priv_ok(self, "description"):
            config = SuiteConfig.get_inst()
            result['title'] = config.cfg['title']
            result['description'] = config.cfg['description']
        if access_priv_ok(self, "state-totals"):
            result['states'] = StateSummaryServer.get_inst().get_state_totals()
        return result

    def id(self):
        # Back-compat for older clients <=6.4.1.
        # (Allows old scan to see new suites.)
        return (self.name, self.owner)

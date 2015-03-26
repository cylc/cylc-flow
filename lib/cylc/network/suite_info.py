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

import sys
import cylc.flags
from cylc.network.pyro_base import PyroClient, PyroServer

PYRO_INFO_OBJ_NAME = 'suite-info'

class SuiteInfoServer(PyroServer):
    """Server-side suite information interface."""

    def __init__(self, info_commands):
        super(SuiteInfoServer, self).__init__()
        self.commands = info_commands

    def get(self, command, *command_args):
        return self.commands[command](*command_args)


class SuiteInfoClient(PyroClient):
    """Client-side suite information interface."""

    target_server_object = PYRO_INFO_OBJ_NAME

    def get_info_gui(self, command, *command_args):
        """GUI suite info interface."""
        self._report(command)
        return self.pyro_proxy.get(command, *command_args)

    def get_info(self, command, *command_args):
        """CLI suite info interface."""
        try:
            return self.get_info_gui(command, *command_args)
        except Exception, x:
            if cylc.flags.debug:
                raise
            sys.exit(x)

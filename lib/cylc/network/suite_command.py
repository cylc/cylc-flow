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
from Queue import Queue
import cylc.flags
from cylc.network.pyro_base import PyroClient, PyroServer

PYRO_CMD_OBJ_NAME = 'command-interface'

class SuiteCommandServer(PyroServer):
    """Server-side suite command interface."""

    def __init__(self, legal_commands=[]):
        super(SuiteCommandServer, self).__init__()
        self.legal = legal_commands
        self.queue = Queue()

    def put(self, command, *command_args):
        if command not in self.legal:
            return (False, 'ERROR: Illegal command: %s' % command)
        else:
            self.queue.put((command, command_args))
            return (True, 'Command queued')

    def get_queue(self):
        return self.queue


class SuiteCommandClient(PyroClient):
    """Client-side suite command interface."""

    target_server_object = PYRO_CMD_OBJ_NAME

    def put_command_gui(self, command, *command_args):
        """GUI suite command interface."""
        self._report(command)
        return self.pyro_proxy.put(command, *command_args)

    def put_command(self, command, *command_args):
        """CLI suite command interface."""
        try:
            success, msg = self.put_command_gui(command, *command_args)
        except Exception as exc:
            if cylc.flags.debug:
                raise
            sys.exit(exc)
        if success:
            print msg
        else:
            sys.exit(msg)

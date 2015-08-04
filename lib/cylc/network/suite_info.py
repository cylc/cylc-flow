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
from cylc.network import PYRO_INFO_OBJ_NAME
from cylc.network.pyro_base import PyroClient, PyroServer
from cylc.network import check_access_priv


# Back-compat for older suite daemons <= 6.4.1.
back_compat = {
    'ping_suite': 'ping suite',
    'ping_task': 'ping task',
    'get_suite_info': 'suite info',
    'get_task_info': 'task info',
    'get_all_families': 'all families',
    'get_triggering_families': 'triggering families',
    'get_first_parent_ancestors': 'first-parent ancestors',
    'get_first_parent_descendants': 'first-parent descendants',
    'get_graph_raw': 'graph raw',
    'get_task_requisites': 'task requisites',
    'get_cylc_version': 'get cylc version',
    'get_task_jobfile_path': 'task job file path'
}


class SuiteInfoServer(PyroServer):
    """Server-side suite information interface."""

    def __init__(self, info_commands):
        super(SuiteInfoServer, self).__init__()
        self.commands = info_commands

    def get(self, command, *command_args):
        if ('ping' in command or 'version' in command):
            # Free info.
            pass
        elif 'suite' in command and 'info' in command:
            # Suite title and description only.
            check_access_priv(self, 'description')
        else:
            check_access_priv(self, 'full-read')
        self.report(command)
        return self.commands[command](*command_args)


class SuiteInfoClient(PyroClient):
    """Client-side suite information interface."""

    target_server_object = PYRO_INFO_OBJ_NAME

    def get_info(self, *args):
        try:
            return self.call_server_func("get", *args)
        except KeyError:
            # Back-compat for older suite daemons <= 6.4.1.
            command = back_compat[args[0]]
            args = tuple([command]) + args[1:]
            return self.call_server_func("get", *args)

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
ILLEGAL_CMD_MSG = 'ERROR: Illegal command:'

# Backward compatibility for suite daemons running at <= 6.4.0.
# TODO - this should eventually be removed.
back_compat = {
    'set_stop_cleanly': 'stop cleanly',
    'stop_now': 'stop now',
    'set_stop_after_point': 'stop after point',
    'set_stop_after_clock_time': 'stop after clock time',
    'set_stop_after_task': 'stop after task',
    'release_suite': 'release suite',
    'release_task': 'release task',
    'remove_cycle': 'remove cycle',
    'remove_task': 'remove task',
    'hold_suite': 'hold suite now',
    'hold_after_point_string': 'hold suite after',
    'hold_task': 'hold task now',
    'set_runahead': 'set runahead',
    'set_verbosity': 'set verbosity',
    'purge_tree': 'purge tree',
    'reset_task_state': 'reset task state',
    'trigger_task': 'trigger task',
    'dry_run_task': 'dry run task',
    'nudge': 'nudge suite',
    'insert_task': 'insert task',
    'reload_suite': 'reload suite',
    'add_prerequisite': 'add prerequisite',
    'poll_tasks': 'poll tasks',
    'kill_tasks': 'kill tasks',
}


class SuiteCommandServer(PyroServer):
    """Server-side suite command interface."""

    def __init__(self, legal_commands=[]):
        super(SuiteCommandServer, self).__init__()
        self.legal = legal_commands
        self.queue = Queue()

    def put(self, command, *command_args):
        if command not in self.legal:
            # TODO - an illegal command indicates a programming error, not a
            # user error, so we shouldn't bother with this.
            return (False, '%s: %s' % (ILLEGAL_CMD_MSG, command))
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
        success, msg = self.pyro_proxy.put(command, *command_args)
        if msg.startswith(ILLEGAL_CMD_MSG):
            # Back compat.
            success, msg = self.put_command_gui(
                back_compat[command], *command_args)
        return success, msg


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

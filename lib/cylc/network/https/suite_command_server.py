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

import ast
from Queue import Queue

from cylc.network.https.base_server import BaseCommsServer
from cylc.network import check_access_priv

import cherrypy


class SuiteCommandServer(BaseCommsServer):
    """Server-side suite command interface."""

    def __init__(self):
        super(SuiteCommandServer, self).__init__()
        self.queue = Queue()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_cleanly(self, kill_active_tasks=False):
        if isinstance(kill_active_tasks, basestring):
            kill_active_tasks = ast.literal_eval(kill_active_tasks)
        return self._put("set_stop_cleanly",
                         None, {"kill_active_tasks": kill_active_tasks})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stop_now(self, terminate=False):
        if isinstance(terminate, basestring):
            terminate = ast.literal_eval(terminate)
        return self._put("stop_now", None, {"terminate": terminate})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_point(self, point_string):
        return self._put("set_stop_after_point", (point_string,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_clock_time(self, datetime_string):
        return self._put("set_stop_after_clock_time", (datetime_string,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_task(self, task_id):
        return self._put("set_stop_after_task", (task_id,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def release_suite(self):
        return self._put("release_suite", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def release_tasks(self, items):
        if not isinstance(items, list):
            items = [items]
        return self._put("release_tasks", (items,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def remove_cycle(self, point_string, spawn=False):
        spawn = ast.literal_eval(spawn)
        return self._put("remove_cycle", (point_string,), {"spawn": spawn})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def remove_tasks(self, items, spawn=False):
        spawn = ast.literal_eval(spawn)
        if not isinstance(items, list):
            items = [items]
        return self._put("remove_tasks", (items,), {"spawn": spawn})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_suite(self):
        return self._put("hold_suite", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_after_point_string(self, point_string):
        return self._put("hold_after_point_string", (point_string,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_tasks(self, items):
        if not isinstance(items, list):
            items = [items]
        return self._put("hold_tasks", (items,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_runahead(self, interval=None):
        interval = ast.literal_eval(interval)
        return self._put("set_runahead", None, {"interval": interval})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_verbosity(self, level):
        return self._put("set_verbosity", (level,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def reset_task_states(self, items, state=None, outputs=None):
        if not isinstance(items, list):
            items = [items]
        if outputs and not isinstance(outputs, list):
            outputs = [outputs]
        return self._put(
            "reset_task_states",
            (items,), {"state": state, "outputs": outputs})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def trigger_tasks(self, items):
        if not isinstance(items, list):
            items = [items]
        items = [str(item) for item in items]
        return self._put("trigger_tasks", (items,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def dry_run_tasks(self, items):
        if not isinstance(items, list):
            items = [items]
        return self._put("dry_run_tasks", (items,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def nudge(self):
        return self._put("nudge", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def insert_tasks(self, items, stop_point_string=None, no_check=False):
        if not isinstance(items, list):
            items = [items]
        if stop_point_string == "None":
            stop_point_string = None
        return self._put("insert_tasks", (items,),
                         {"stop_point_string": stop_point_string,
                          "no_check": no_check in ['True', True]})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def reload_suite(self):
        return self._put("reload_suite", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def poll_tasks(self, items=None):
        if items is not None and not isinstance(items, list):
            items = [items]
        return self._put("poll_tasks", (items,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def kill_tasks(self, items):
        if not isinstance(items, list):
            items = [items]
        return self._put("kill_tasks", (items,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def spawn_tasks(self, items):
        if not isinstance(items, list):
            items = [items]
        return self._put("spawn_tasks", (items,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def take_checkpoints(self, items):
        if not isinstance(items, list):
            items = [items]
        return self._put("take_checkpoints", (items,))

    def _put(self, command, command_args, command_kwargs=None):
        if command_args is None:
            command_args = tuple()
        if command_kwargs is None:
            command_kwargs = {}
        if 'stop' in command:
            check_access_priv(self, 'shutdown')
        else:
            check_access_priv(self, 'full-control')
        self.report(command)
        self.queue.put((command, command_args, command_kwargs))
        return (True, 'Command queued')

    def get_queue(self):
        return self.queue

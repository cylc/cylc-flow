#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
import sys
import os
from Queue import Queue

import cylc.flags
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
        """Command to stop the suite after current active tasks finish.

        Example URLs:

        * /set_stop_cleanly
        * /set_stop_cleanly?kill_active_tasks=True

        Kwargs:

        * kill_active_tasks - boolean
            If kill_active_tasks is True, kill all current tasks before
            stopping.

        """
        if isinstance(kill_active_tasks, basestring):
            kill_active_tasks = ast.literal_eval(kill_active_tasks)
        return self._put("set_stop_cleanly",
                         None, {"kill_active_tasks": kill_active_tasks})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stop_now(self, terminate=False):
        """Command to stop the suite right now, orphaning current active tasks.

        By default, wait for event handlers to finish.

        Example URLs:

        * /stop_now
        * /stop_now?terminate=True

        Kwargs:

        * terminate - boolean
            If terminate is True, terminate without waiting for event
            handlers to finish.

        """
        if isinstance(terminate, basestring):
            terminate = ast.literal_eval(terminate)
        return self._put("stop_now", None, {"terminate": terminate})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_point(self, point_string):
        """Command to stop the suite after a cycle point.

        Example URL:

        * /set_stop_after_point?point_string=20101225T0000Z

        Args:

        * point_string - string
            point_string should be a valid cycle point for the suite.

        """
        return self._put("set_stop_after_point", (point_string,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_clock_time(self, datetime_string):
        """Command to stop the suite after a wallclock time has been reached.

        Example URL:

        * /set_stop_after_clock_time?datetime_string=2016-11-01T15:43+11

        Args:

        * datetime_string - string
            datetime_string should be a valid ISO 8601 date-time.

        """
        return self._put("set_stop_after_clock_time", (datetime_string,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_task(self, task_id):
        """Command to stop the suite after a particular task succeeds.

        Example URL:

        * /set_stop_after_task?task_id=foo.20160101T0000Z

        Args:

        * task_id - string
            task_id should be the task whose success triggers a shut
            down.

        """
        return self._put("set_stop_after_task", (task_id,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def release_suite(self):
        """Command to release or unpause the suite from a held state.

        Example URL:

        * /release_suite

        """
        return self._put("release_suite", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def release_tasks(self, task_ids):
        """Command to release particular tasks from a held state.

        Example URL:

        * /release_tasks?task_ids=foo.20160101T0000Z&task_ids=20160201T0000Z%2F%2A

        Args:

        * task_ids - list or string
            task_ids should be either a single task id spec or a list of
            task id spec to release.

        """
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        return self._put("release_tasks", (task_ids,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def remove_cycle(self, point_string, spawn=False):
        """Command to remove a cycle point from the suite.

        Example URL:

        * /remove_cycle?point_string=20160101T0000Z
        * /remove_cycle?point_string=20161225T0632+13&spawn=True

        Args:

        * point_string - string
            point_string should be the cycle point to remove.

        Kwargs:

        * spawn - boolean
            spawn, if True, allows the removed tasks in that cycle
            point to spawn their successors.

        """
        spawn = ast.literal_eval(spawn)
        return self._put("remove_cycle", (point_string,), {"spawn": spawn})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def remove_tasks(self, task_ids, spawn=False):
        """Command to remove a particular task or tasks from the suite.

        Example URL:

        * /release_tasks?task_ids=foo.20160101T0000Z&task_ids=20160201T0000Z%2F%2A

        Args:

        * task_ids - list or string
            task_ids should either be a string of a task id spec to remove
            or a list of task id specs to remove.

        Kwargs:

        * spawn - boolean
            spawn, if True, allows the removed task or tasks to spawn
            their successors.

        """
        spawn = ast.literal_eval(spawn)
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        return self._put("remove_tasks", (task_ids,), {"spawn": spawn})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_suite(self):
        """Command to hold (pause) a suite.

        Example URL:

        * /hold_suite

        """
        return self._put("hold_suite", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_after_point_string(self, point_string):
        """Command to hold a suite after a cycle point.

        Example URL:

        * /hold_after_point_string?point_string=20160101T0000Z

        Args:

        * point_string - string
            point_string should be the cycle point to hold the suite
            after.

        """
        return self._put("hold_after_point_string", (point_string,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_tasks(self, task_ids):
        """Command to hold or pause a particular task or tasks.

        Example URLs:

        * /hold_tasks?task_ids=foo.%2A
        * /hold_tasks?task_ids=foo.2&task_ids=bar.1

        Args:

        * task_ids - list or string
            task_ids should either be a string of a task id spec to hold
            or a list of task id specs to hold.

        """
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        return self._put("hold_tasks", (task_ids,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_runahead(self, interval=None):
        """Command to set or reset the suite runahead limit.

        Example URLs:

        * /set_runahead
        * /set_runahead?interval=PT6H

        Kwargs:

        * interval - ISO 8601 duration string or None
            interval should be a string like 'PT36H' to set this as the
            suite runahead limit or None to clear the suite runahead
            limit.

        """
        interval = ast.literal_eval(interval)
        return self._put("set_runahead", None, {"interval": interval})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_verbosity(self, level):
        """Command to set the suite logging verbosity.

        Example URL:

        * /set_verbosity?level=DEBUG

        Args:

        * level - string
            level should be the new suite logging level - one of 'INFO',
            'NORMAL', 'WARNING', 'ERROR', 'CRITICAL', 'DEBUG'.

        """
        return self._put("set_verbosity", (level,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def reset_task_states(self, task_ids, state):
        """Command to reset the state of a particular task or tasks.

        Example URL:

        * /reset_task_states?task_ids=foo.1&state=waiting

        Args:

        * task_ids - list or string
            task_ids should either be a string of a task id spec to reset
            or a list of task id specs to reset.
        * state - string
            state should be the destination state e.g. 'waiting' or
            'succeeded'.

        """
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        return self._put("reset_task_states", (task_ids,), {"state": state})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def trigger_tasks(self, task_ids):
        """Command to trigger a particular task or tasks.

        Example URLs:

        * /trigger_tasks?task_ids=foo.20160101T0000Z
        * /trigger_tasks?task_ids=foo.1&task_ids=bar.1
        * /trigger_tasks?task_ids=:failed

        Args:

        * task_ids - list or string
            task_ids should either be a string of a task id spec to trigger
            or a list of task id specs to trigger.

        """
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        task_ids = [str(item) for item in task_ids]
        return self._put("trigger_tasks", (task_ids,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def dry_run_tasks(self, task_ids):
        """Command to dry run a particular task or tasks.

        Example URLs:

        * /dry_run_tasks?task_ids=foo.1

        This generates job files but does not submit them - e.g. for
        an edit run.

        Args:

        * task_ids - list or string
            task_ids should either be a string of a task id spec to dry
            run or a list of task id specs to dry run.

        """
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        return self._put("dry_run_tasks", (task_ids,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def nudge(self):
        """Command to nudge cylc task processing in case of stuck suites.

        Example URL:

        * /nudge

        """
        return self._put("nudge", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def insert_tasks(self, task_ids, stop_point_string=None):
        """Command to insert a task or tasks.

        Example URLs:

        * /insert_tasks?task_ids=foo.20160101
        * /insert_tasks?task_ids=foo.20160101&stop_point_string=20161225

        Args:

        * task_ids - list or string
            task_ids should either be a string of a task id spec to insert
            or a list of task id specs to insert.

        Kwargs:

        * stop_point_string - string or None
            stop_point_string, if given, sets a stop cycle point for
            the task or tasks that they will not spawn beyond.

        """
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        if stop_point_string == "None":
            stop_point_string = None
        return self._put("insert_tasks", (task_ids,),
                         {"stop_point_string": stop_point_string})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def reload_suite(self):
        """Command to reload the suite definition from files.

        Example URLs:

        * /reload_suite

        """
        return self._put("reload_suite", None)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def poll_tasks(self, task_ids=None):
        """Command to poll particular tasks or all in the suite.

        Example URL:

        * /poll_tasks
        * /poll_tasks?task_ids=foo.20160101

        Kwargs:

        * task_ids - list or string or None
            task_ids, if None, implies that all tasks should be polled.
            task_ids can also either be a string of a task id spec to
            poll or a list of task id specs to poll.

        """
        if task_ids is not None and not isinstance(task_ids, list):
            task_ids = [task_ids]
        return self._put("poll_tasks", (task_ids,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def kill_tasks(self, task_ids):
        """Command to kill a task or tasks.

        Example URLs:

        * /kill_tasks?task_ids=foo.1&task_ids=bar.1
        * /kill_tasks?task_ids=:running

        Args:

        * task_ids - list or string
            task_ids should either be a string of a task id spec to kill
            or a list of task id specs to insert.

        """
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        return self._put("kill_tasks", (task_ids,))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def spawn_tasks(self, task_ids):
        """Command to spawn the successors of a task or tasks.

        Example URLs:

        * /spawn_tasks?task_ids=foo.1&task_ids=bar.1
        * /spawn_tasks?task_ids=FOO

        Args:

        * task_ids - list or string
            task_ids should either be a string of a task id spec to spawn
            or a list of task id specs to spawn.

        """
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        return self._put("spawn_tasks", (task_ids,))

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

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
"""Suite server-side API implementation."""

import ast
import cherrypy
import inspect
from time import time

import cylc.flags
from cylc.network import PRIVILEGE_LEVELS
from cylc.network.server_util import get_client_info
from cylc.suite_logging import LOG
from cylc.unicode_util import unicode_encode
from cylc.version import CYLC_VERSION


class SuiteRuntimeService(object):
    """Suite runtime service API facade."""

    CLIENT_FORGET_SEC = 60
    CLIENT_ID_MIN_REPORT_RATE = 1.0  # 1 Hz
    CLIENT_ID_REPORT_SECONDS = 3600  # Report every 1 hour.
    CONNECT_DENIED_PRIV_TMPL = (
        "[client-connect] DENIED (privilege '%s' < '%s') %s@%s:%s %s")
    LOG_COMMAND_TMPL = '[client-command] %s %s@%s:%s %s'
    LOG_IDENTIFY_TMPL = '[client-identify] %d id requests in PT%dS'
    LOG_FORGET_TMPL = '[client-forget] %s'
    LOG_CONNECT_ALLOWED_TMPL = "[client-connect] %s@%s:%s privilege='%s' %s"

    def __init__(self, schd):
        self.schd = schd
        self.clients = {}  # {uuid: time-of-last-connect}
        self._id_start_time = time()  # Start of id requests measurement.
        self._num_id_requests = 0  # Number of client id requests.

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def clear_broadcast(
            self, point_strings=None, namespaces=None, cancel_settings=None):
        """Clear settings globally, or for listed namespaces and/or points.

        Return a tuple (modified_settings, bad_options), where:
        * modified_settings is similar to the return value of the "put" method,
          but for removed settings.
        * bad_options is a dict in the form:
              {"point_strings": ["20020202", ..."], ...}
          The dict is only populated if there are options not associated with
          previous broadcasts. The keys can be:
          * point_strings: a list of bad point strings.
          * namespaces: a list of bad namespaces.
          * cancel: a list of tuples. Each tuple contains the keys of a bad
            setting.
        """
        self._check_access_priv('full-control')
        self._report()
        point_strings = unicode_encode(
            cherrypy.request.json.get("point_strings", point_strings))
        namespaces = unicode_encode(
            cherrypy.request.json.get("namespaces", namespaces))
        cancel_settings = unicode_encode(
            cherrypy.request.json.get("cancel_settings", cancel_settings))
        return self.schd.task_events_mgr.broadcast_mgr.clear_broadcast(
            point_strings, namespaces, cancel_settings)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def dry_run_tasks(self, items):
        """Prepare job file for a task.

        items[0] is an identifier for matching a task proxy.
        """
        self._check_access_priv('full-control')
        self._report()
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("dry_run_tasks", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def expire_broadcast(self, cutoff=None):
        """Clear all settings targeting cycle points earlier than cutoff."""
        self._check_access_priv('full-control')
        self._report()
        return self.schd.task_events_mgr.broadcast_mgr.expire_broadcast(cutoff)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_all_families(self, exclude_root=False):
        """Return info of all families."""
        self._check_access_priv('full-read')
        self._report()
        if isinstance(exclude_root, basestring):
            exclude_root = ast.literal_eval(exclude_root)
        return self.schd.info_get_all_families(exclude_root=exclude_root)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_broadcast(self, task_id=None):
        """Retrieve all broadcast variables that target a given task ID."""
        self._check_access_priv('full-read')
        self._report()
        return self.schd.task_events_mgr.broadcast_mgr.get_broadcast(task_id)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_cylc_version(self):
        """Return the cylc version running this suite daemon."""
        self._report()
        return CYLC_VERSION

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_err_content(self, prev_size, max_lines):
        """Return the content and new size of the error file."""
        self._check_access_priv('full-read')
        self._report()
        return self.schd.info_get_err_lines(prev_size, max_lines)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_first_parent_ancestors(self, pruned=None):
        """Single-inheritance hierarchy based on first parents"""
        self._report()
        self._check_access_priv('full-read')
        if isinstance(pruned, basestring):
            pruned = ast.literal_eval(pruned)
        return self.schd.info_get_first_parent_ancestors(pruned=pruned)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_first_parent_descendants(self):
        """Families for single-inheritance hierarchy based on first parents"""
        self._report()
        self._check_access_priv('full-read')
        return self.schd.info_get_first_parent_descendants()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_graph_raw(self, start_point_string, stop_point_string,
                      group_nodes=None, ungroup_nodes=None,
                      ungroup_recursive=False, group_all=False,
                      ungroup_all=False):
        """Return raw suite graph."""
        self._check_access_priv('full-read')
        self._report()
        if isinstance(group_nodes, basestring):
            try:
                group_nodes = ast.literal_eval(group_nodes)
            except ValueError:
                group_nodes = [group_nodes]
        if isinstance(ungroup_nodes, basestring):
            try:
                ungroup_nodes = ast.literal_eval(ungroup_nodes)
            except ValueError:
                ungroup_nodes = [ungroup_nodes]
        if isinstance(ungroup_recursive, basestring):
            ungroup_recursive = ast.literal_eval(ungroup_recursive)
        if isinstance(group_all, basestring):
            group_all = ast.literal_eval(group_all)
        if isinstance(ungroup_all, basestring):
            ungroup_all = ast.literal_eval(ungroup_all)
        if isinstance(stop_point_string, basestring):
            try:
                stop_point_string = ast.literal_eval(stop_point_string)
            except (SyntaxError, ValueError):
                pass
            else:
                if stop_point_string is not None:
                    stop_point_string = str(stop_point_string)
        return self.schd.info_get_graph_raw(
            start_point_string, stop_point_string,
            group_nodes=group_nodes,
            ungroup_nodes=ungroup_nodes,
            ungroup_recursive=ungroup_recursive,
            group_all=group_all,
            ungroup_all=ungroup_all)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_state_summary(self):
        """Return the global, task, and family summary data structures."""
        self._check_access_priv('full-read')
        self._report()
        return self.schd.info_get_state_summary()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_suite_info(self):
        """Return a dict containing the suite title and description."""
        self._report()
        self._check_access_priv('description')
        return self.schd.info_get_suite_info()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_info(self, names):
        """Return info of a task."""
        self._report()
        self._check_access_priv('full-read')
        if not isinstance(names, list):
            names = [names]
        return self.schd.info_get_task_info(names)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_jobfile_path(self, task_id):
        """Return task job file path."""
        self._report()
        self._check_access_priv('full-read')
        return self.schd.info_get_task_jobfile_path(task_id)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_requisites(self, items=None, list_prereqs=False):
        """Return prerequisites of a task."""
        self._report()
        self._check_access_priv('full-read')
        if not isinstance(items, list):
            items = [items]
        return self.schd.info_get_task_requisites(
            items, list_prereqs=(list_prereqs in [True, 'True']))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_update_times(self):
        """Return the update times for (state summary, err_content)."""
        self._check_access_priv('state-totals')
        self._report()
        return self.schd.info_get_update_times()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_after_point_string(self, point_string):
        """Set hold point of suite."""
        self._check_access_priv('full-control')
        self._report()
        self.schd.command_queue.put(
            ("hold_after_point_string", (point_string,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_suite(self):
        """Hold the suite."""
        self._check_access_priv('full-control')
        self._report()
        self.schd.command_queue.put(("hold_suite", (), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_tasks(self, items):
        """Hold tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv('full-control')
        self._report()
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("hold_tasks", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def identify(self):
        """Return suite identity, (description, (states))."""
        self._report_id_requests()
        privileges = []
        for privilege in PRIVILEGE_LEVELS[0:3]:
            if self._access_priv_ok(privilege):
                privileges.append(privilege)
        return self.schd.info_get_identity(privileges)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def insert_tasks(self, items, stop_point_string=None, no_check=False):
        """Insert task proxies.

        items is a list of identifiers of (families of) task instances.
        """
        self._check_access_priv('full-control')
        self._report()
        if not isinstance(items, list):
            items = [items]
        if stop_point_string == "None":
            stop_point_string = None
        self.schd.command_queue.put((
            "insert_tasks",
            (items,),
            {"stop_point_string": stop_point_string,
             "no_check": no_check in ['True', True]}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def kill_tasks(self, items):
        """Kill task jobs.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv('full-control')
        self._report()
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("kill_tasks", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def nudge(self):
        """Tell suite to try task processing."""
        self._check_access_priv('full-control')
        self._report()
        self.schd.command_queue.put(("nudge", (), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping_suite(self):
        """Return True."""
        self._report()
        return True

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping_task(self, task_id, exists_only=False):
        """Return True if task_id exists (and running)."""
        self._check_access_priv('full-read')
        self._report()
        if isinstance(exists_only, basestring):
            exists_only = ast.literal_eval(exists_only)
        return self.schd.info_ping_task(task_id, exists_only=exists_only)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def poll_tasks(self, items=None):
        """Poll task jobs.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv('full-control')
        self._report()
        if items is not None and not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("poll_tasks", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def put_broadcast(
            self, point_strings=None, namespaces=None, settings=None):
        """Add new broadcast settings (server side interface).

        Return a tuple (modified_settings, bad_options) where:
          modified_settings is list of modified settings in the form:
            [("20200202", "foo", {"command scripting": "true"}, ...]
          bad_options is as described in the docstring for self.clear().
        """
        self._check_access_priv('full-control')
        self._report()
        point_strings = unicode_encode(
            cherrypy.request.json.get("point_strings", point_strings))
        namespaces = unicode_encode(
            cherrypy.request.json.get("namespaces", namespaces))
        settings = unicode_encode(
            cherrypy.request.json.get("settings", settings))
        return self.schd.task_events_mgr.broadcast_mgr.put_broadcast(
            point_strings, namespaces, settings)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def put_ext_trigger(self, event_message, event_id):
        """Server-side external event trigger interface."""
        self._check_access_priv('full-control')
        self._report()
        self.schd.ext_trigger_queue.put((event_message, event_id))
        return (True, 'Event queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def put_message(self, task_id, priority, message):
        self._check_access_priv('full-control')
        self._report()
        self.schd.message_queue.put((task_id, priority, str(message)))
        return (True, 'Message queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def reload_suite(self):
        """Tell suite to reload the suite definition."""
        self._check_access_priv('full-control')
        self._report()
        self.schd.command_queue.put(("reload_suite", (), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def release_suite(self):
        """Unhold suite."""
        self._check_access_priv('full-control')
        self._report()
        self.schd.command_queue.put(("release_suite", (), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def release_tasks(self, items):
        """Unhold tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv('full-control')
        self._report()
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("release_tasks", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def remove_cycle(self, point_string, spawn=False):
        """Remove tasks in a cycle from task pool."""
        self._check_access_priv('full-control')
        self._report()
        spawn = ast.literal_eval(spawn)
        self.schd.command_queue.put(
            ("remove_tasks", ('%s/*' % point_string,), {"spawn": spawn}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def remove_tasks(self, items, spawn=False):
        """Remove tasks from task pool.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv('full-control')
        self._report()
        spawn = ast.literal_eval(spawn)
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(
            ("remove_tasks", (items,), {"spawn": spawn}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def reset_task_states(self, items, state=None, outputs=None):
        """Reset statuses tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv('full-control')
        self._report()
        if not isinstance(items, list):
            items = [items]
        if outputs and not isinstance(outputs, list):
            outputs = [outputs]
        self.schd.command_queue.put((
            "reset_task_states",
            (items,), {"state": state, "outputs": outputs}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_runahead(self, interval=None):
        """Set runahead limit to a new interval."""
        self._check_access_priv('full-control')
        self._report()
        interval = ast.literal_eval(interval)
        self.schd.command_queue.put(
            ("set_runahead", (), {"interval": interval}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_clock_time(self, datetime_string):
        """Set suite to stop after wallclock time."""
        self._check_access_priv('shutdown')
        self._report()
        self.schd.command_queue.put(
            ("set_stop_after_clock_time", (datetime_string,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_point(self, point_string):
        """Set suite to stop after cycle point."""
        self._check_access_priv('shutdown')
        self._report()
        self.schd.command_queue.put(
            ("set_stop_after_point", (point_string,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_task(self, task_id):
        """Set suite to stop after an instance of a task."""
        self._check_access_priv('shutdown')
        self._report()
        self.schd.command_queue.put(
            ("set_stop_after_task", (task_id,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_cleanly(self, kill_active_tasks=False):
        """Set suite to stop cleanly or after kill active tasks."""
        self._check_access_priv('shutdown')
        self._report()
        if isinstance(kill_active_tasks, basestring):
            kill_active_tasks = ast.literal_eval(kill_active_tasks)
        self.schd.command_queue.put(
            ("set_stop_cleanly", (), {"kill_active_tasks": kill_active_tasks}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_verbosity(self, level):
        """Set suite verbosity to new level."""
        self._check_access_priv('full-control')
        self._report()
        self.schd.command_queue.put(("set_verbosity", (level,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def spawn_tasks(self, items):
        """Spawn tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv('full-control')
        self._report()
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("spawn_tasks", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stop_now(self, terminate=False):
        """Stop suite on event handler completion, or terminate right away."""
        self._check_access_priv('shutdown')
        self._report()
        if isinstance(terminate, basestring):
            terminate = ast.literal_eval(terminate)
        self.schd.command_queue.put(("stop_now", (), {"terminate": terminate}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def take_checkpoints(self, items):
        """Checkpoint current task pool.

        items[0] is the name of the checkpoint.
        """
        self._check_access_priv('full-control')
        self._report()
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("take_checkpoints", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def trigger_tasks(self, items):
        """Trigger submission of task jobs where possible.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv('full-control')
        self._report()
        if not isinstance(items, list):
            items = [items]
        items = [str(item) for item in items]
        self.schd.command_queue.put(("trigger_tasks", (items,), {}))
        return (True, 'Command queued')

    def _access_priv_ok(self, required_privilege_level):
        """Return True if a client is allowed access to info from server_obj.

        The required privilege level is compared to the level granted to the
        client by the connection validator (held in thread local storage).

        """
        try:
            return self._check_access_priv(required_privilege_level)
        except cherrypy.HTTPError:
            return False

    def _check_access_priv(self, required_privilege_level):
        """Raise an exception if client privilege is insufficient for server_obj.

        (See the documentation above for the boolean version of this function).

        """
        auth_user, prog_name, user, host, uuid = get_client_info()
        priv_level = self._get_priv_level(auth_user)
        if (PRIVILEGE_LEVELS.index(priv_level) <
                PRIVILEGE_LEVELS.index(required_privilege_level)):
            err = self.CONNECT_DENIED_PRIV_TMPL % (
                priv_level, required_privilege_level,
                user, host, prog_name, uuid)
            LOG.warning(err)
            # Raise an exception to be sent back to the client.
            raise cherrypy.HTTPError(403, err)
        return True

    def _report(self):
        """Log client requests with identifying information.

        In debug mode log all requests including task messages. Otherwise log
        all user commands, and just the first info command from each client.

        """
        command = inspect.currentframe().f_back.f_code.co_name
        auth_user, prog_name, user, host, uuid = get_client_info()
        priv_level = self._get_priv_level(auth_user)
        LOG.debug(self.__class__.LOG_CONNECT_ALLOWED_TMPL % (
            user, host, prog_name, priv_level, uuid))
        LOG.info(self.__class__.LOG_COMMAND_TMPL % (
            command, user, host, prog_name, uuid))
        self.clients[uuid] = time()
        self._housekeep()

    def _report_id_requests(self):
        """Report the frequency of identification (scan) requests."""
        self._num_id_requests += 1
        now = time()
        interval = now - self._id_start_time
        if interval > self.CLIENT_ID_REPORT_SECONDS:
            rate = float(self._num_id_requests) / interval
            if rate > self.CLIENT_ID_MIN_REPORT_RATE:
                log = LOG.warning
            elif cylc.flags.debug:
                log = LOG.info
            log(self.__class__.LOG_IDENTIFY_TMPL % (
                self._num_id_requests, interval))
            self._id_start_time = now
            self._num_id_requests = 0
        self.clients[get_client_info()[4]] = now
        self._housekeep()

    def _get_priv_level(self, auth_user):
        """Get the privilege level for this authenticated user."""
        if auth_user == "cylc":
            return PRIVILEGE_LEVELS[-1]
        return self.schd.config.cfg['cylc']['authentication']['public']

    def _housekeep(self):
        """Forget inactive clients."""
        for uuid, dtime in self.clients.copy().items():
            if time() - dtime > self.CLIENT_FORGET_SEC:
                try:
                    del self.clients[uuid]
                except KeyError:
                    pass
                LOG.debug(
                    self.__class__.LOG_FORGET_TMPL % uuid)

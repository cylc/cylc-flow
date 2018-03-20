#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
"""HTTP(S) server, and suite runtime API service facade exposed.

Implementation currently via cherrypy.
"""

import ast
import binascii
import inspect
import os
import random
from time import time
import traceback
from uuid import uuid4

import cherrypy
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import CylcError
import cylc.flags
from cylc.network import (
    NO_PASSPHRASE, PRIVILEGE_LEVELS, PRIV_IDENTITY, PRIV_DESCRIPTION,
    PRIV_FULL_READ, PRIV_SHUTDOWN, PRIV_FULL_CONTROL)
from cylc.hostuserutil import get_host
from cylc.suite_logging import ERR, LOG
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.unicode_util import utf8_enforce
from cylc.version import CYLC_VERSION


class HTTPServer(object):
    """HTTP(S) server by cherrypy, for serving suite runtime API."""

    API = 1
    LOG_CONNECT_DENIED_TMPL = "[client-connect] DENIED %s@%s:%s %s"

    def __init__(self, suite):
        # Suite only needed for back-compat with old clients (see below):
        self.suite = suite
        self.engine = None
        self.port = None

        # Figure out the ports we are allowed to use.
        base_port = glbl_cfg().get(['communication', 'base port'])
        max_ports = glbl_cfg().get(
            ['communication', 'maximum number of ports'])
        self.ok_ports = range(int(base_port), int(base_port) + int(max_ports))
        random.shuffle(self.ok_ports)

        comms_options = glbl_cfg().get(['communication', 'options'])

        # HTTP Digest Auth uses MD5 - pretty secure in this use case.
        # Extending it with extra algorithms is allowed, but won't be
        # supported by most browsers. requests and urllib2 are OK though.
        self.hash_algorithm = "MD5"
        if "SHA1" in comms_options:
            # Note 'SHA' rather than 'SHA1'.
            self.hash_algorithm = "SHA"

        self.srv_files_mgr = SuiteSrvFilesManager()
        self.comms_method = glbl_cfg().get(['communication', 'method'])
        self.get_ha1 = cherrypy.lib.auth_digest.get_ha1_dict_plain(
            {
                'cylc': self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_PASSPHRASE,
                    suite, content=True),
                'anon': NO_PASSPHRASE
            },
            algorithm=self.hash_algorithm)
        if self.comms_method == 'http':
            self.cert = None
            self.pkey = None
        else:  # if self.comms_method in [None, 'https']:
            try:
                self.cert = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_SSL_CERT, suite)
                self.pkey = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_SSL_PEM, suite)
            except SuiteServiceFileError:
                ERR.error("no HTTPS/OpenSSL support. Aborting...")
                raise CylcError("No HTTPS support. "
                                "Configure user's global.rc to use HTTP.")
        self.start()

    @cherrypy.expose
    def apiversion(self):
        """Return API version."""
        return str(self.API)

    @staticmethod
    def connect(schd):
        """Mount suite schedular object to the web server."""
        cherrypy.tree.mount(SuiteRuntimeService(schd), '/')
        # For back-compat with "scan"
        cherrypy.tree.mount(SuiteRuntimeService(schd), '/id')

    @staticmethod
    def disconnect(schd):
        """Disconnect obj from the web server."""
        del cherrypy.tree.apps['/%s/%s' % (schd.owner, schd.suite)]

    def get_port(self):
        """Return the web server port."""
        return self.port

    def shutdown(self):
        """Shutdown the web server."""
        if hasattr(self, "engine"):
            self.engine.exit()
            self.engine.block()

    def start(self):
        """Start quick web service."""
        # cherrypy.config["tools.encode.on"] = True
        # cherrypy.config["tools.encode.encoding"] = "utf-8"
        cherrypy.config["server.socket_host"] = get_host()
        cherrypy.config["engine.autoreload.on"] = False

        if self.comms_method == "https":
            # Setup SSL etc. Otherwise fail and exit.
            # Require connection method to be the same e.g HTTP/HTTPS matching.
            cherrypy.config['server.ssl_module'] = 'pyopenSSL'
            cherrypy.config['server.ssl_certificate'] = self.cert
            cherrypy.config['server.ssl_private_key'] = self.pkey

        cherrypy.config['log.screen'] = None
        key = binascii.hexlify(os.urandom(16))
        cherrypy.config.update({
            'tools.auth_digest.on': True,
            'tools.auth_digest.realm': self.suite,
            'tools.auth_digest.get_ha1': self.get_ha1,
            'tools.auth_digest.key': key,
            'tools.auth_digest.algorithm': self.hash_algorithm
        })
        cherrypy.tools.connect_log = cherrypy.Tool(
            'on_end_resource', self._report_connection_if_denied)
        cherrypy.config['tools.connect_log.on'] = True
        self.engine = cherrypy.engine
        for port in self.ok_ports:
            cherrypy.config["server.socket_port"] = port
            try:
                cherrypy.engine.start()
                cherrypy.engine.wait(cherrypy.engine.states.STARTED)
            except cherrypy.process.wspbus.ChannelFailures:
                if cylc.flags.debug:
                    traceback.print_exc()
                # We need to reinitialise the httpserver for each port attempt.
                cherrypy.server.httpserver = None
            else:
                if cherrypy.engine.state == cherrypy.engine.states.STARTED:
                    self.port = port
                    return
        raise Exception("No available ports")

    @staticmethod
    def _get_client_connection_denied():
        """Return whether a connection was denied."""
        if "Authorization" not in cherrypy.request.headers:
            # Probably just the initial HTTPS handshake.
            return False
        status = cherrypy.response.status
        if isinstance(status, basestring):
            return cherrypy.response.status.split()[0] in ["401", "403"]
        return cherrypy.response.status in [401, 403]

    def _report_connection_if_denied(self):
        """Log an (un?)successful connection attempt."""
        prog_name, user, host, uuid = _get_client_info()[1:]
        connection_denied = self._get_client_connection_denied()
        if connection_denied:
            LOG.warning(self.__class__.LOG_CONNECT_DENIED_TMPL % (
                user, host, prog_name, uuid))


class SuiteRuntimeService(object):
    """Suite runtime service API facade exposed via cherrypy."""

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
        # Client sessions, 'time' is time of latest visit.
        # Some methods may store extra info to the client session dict.
        # {UUID: {'time': TIME, ...}, ...}
        self.clients = {}
        # Start of id requests measurement
        self._id_start_time = time()
        # Number of client id requests
        self._num_id_requests = 0

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
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        point_strings = utf8_enforce(
            cherrypy.request.json.get("point_strings", point_strings))
        namespaces = utf8_enforce(
            cherrypy.request.json.get("namespaces", namespaces))
        cancel_settings = utf8_enforce(
            cherrypy.request.json.get("cancel_settings", cancel_settings))
        return self.schd.task_events_mgr.broadcast_mgr.clear_broadcast(
            point_strings, namespaces, cancel_settings)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def dry_run_tasks(self, items, check_syntax=True):
        """Prepare job file for a task.

        items[0] is an identifier for matching a task proxy.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        if not isinstance(items, list):
            items = [items]
        check_syntax = self._literal_eval('check_syntax', check_syntax)
        self.schd.command_queue.put(('dry_run_tasks', (items,),
                                    {'check_syntax': check_syntax}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def expire_broadcast(self, cutoff=None):
        """Clear all settings targeting cycle points earlier than cutoff."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        return self.schd.task_events_mgr.broadcast_mgr.expire_broadcast(cutoff)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_broadcast(self, task_id=None):
        """Retrieve all broadcast variables that target a given task ID."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        return self.schd.task_events_mgr.broadcast_mgr.get_broadcast(task_id)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_cylc_version(self):
        """Return the cylc version running this suite."""
        self._check_access_priv_and_report(PRIV_IDENTITY)
        return CYLC_VERSION

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_graph_raw(self, start_point_string, stop_point_string,
                      group_nodes=None, ungroup_nodes=None,
                      ungroup_recursive=False, group_all=False,
                      ungroup_all=False):
        """Return raw suite graph."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        group_nodes = self._literal_eval(
            'group_nodes', group_nodes, [group_nodes])
        ungroup_nodes = self._literal_eval(
            'ungroup_nodes', ungroup_nodes, [ungroup_nodes])
        ungroup_recursive = self._literal_eval(
            'ungroup_recursive', ungroup_recursive)
        group_all = self._literal_eval('group_all', group_all)
        ungroup_all = self._literal_eval('ungroup_all', ungroup_all)
        # Ensure that a "None" str is converted to the None value.
        stop_point_string = self._literal_eval(
            'stop_point_string', stop_point_string, stop_point_string)
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
    def get_latest_state(self, full_mode=False):
        """Return latest suite state (suitable for a GUI update)."""
        client_info = self._check_access_priv_and_report(PRIV_FULL_READ)
        full_mode = self._literal_eval('full_mode', full_mode)
        return self.schd.info_get_latest_state(client_info, full_mode)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_suite_info(self):
        """Return a dict containing the suite title and description."""
        self._check_access_priv_and_report(PRIV_DESCRIPTION)
        return self.schd.info_get_suite_info()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_suite_state_summary(self):
        """Return the global, task, and family summary data structures."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        return self.schd.info_get_suite_state_summary()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_info(self, names):
        """Return info of a task."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        if not isinstance(names, list):
            names = [names]
        return self.schd.info_get_task_info(names)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_jobfile_path(self, task_id):
        """Return task job file path."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        return self.schd.info_get_task_jobfile_path(task_id)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_task_requisites(self, items=None, list_prereqs=False):
        """Return prerequisites of a task."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        if not isinstance(items, list):
            items = [items]
        return self.schd.info_get_task_requisites(
            items, list_prereqs=(list_prereqs in [True, 'True']))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_after_point_string(self, point_string):
        """Set hold point of suite."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.schd.command_queue.put(
            ("hold_after_point_string", (point_string,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_suite(self):
        """Hold the suite."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.schd.command_queue.put(("hold_suite", (), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def hold_tasks(self, items):
        """Hold tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
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
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
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
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("kill_tasks", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def nudge(self):
        """Tell suite to try task processing."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.schd.command_queue.put(("nudge", (), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping_suite(self):
        """Return True."""
        self._check_access_priv_and_report(PRIV_IDENTITY)
        return True

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping_task(self, task_id, exists_only=False):
        """Return True if task_id exists (and running)."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        exists_only = self._literal_eval('exists_only', exists_only)
        return self.schd.info_ping_task(task_id, exists_only=exists_only)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def poll_tasks(self, items=None, poll_succ=False):
        """Poll task jobs.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        if items is not None and not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(
            ("poll_tasks", (items,),
                {"poll_succ": poll_succ in ['True', True]}))
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
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        point_strings = utf8_enforce(
            cherrypy.request.json.get("point_strings", point_strings))
        namespaces = utf8_enforce(
            cherrypy.request.json.get("namespaces", namespaces))
        settings = utf8_enforce(
            cherrypy.request.json.get("settings", settings))
        return self.schd.task_events_mgr.broadcast_mgr.put_broadcast(
            point_strings, namespaces, settings)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def put_ext_trigger(self, event_message, event_id):
        """Server-side external event trigger interface."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.schd.ext_trigger_queue.put((event_message, event_id))
        return (True, 'Event queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def put_message(self, task_id, severity, message):
        self._check_access_priv_and_report(PRIV_FULL_CONTROL, log_info=False)
        self.schd.message_queue.put((task_id, severity, str(message)))
        return (True, 'Message queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def reload_suite(self):
        """Tell suite to reload the suite definition."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.schd.command_queue.put(("reload_suite", (), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def release_suite(self):
        """Unhold suite."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.schd.command_queue.put(("release_suite", (), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def release_tasks(self, items):
        """Unhold tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("release_tasks", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def remove_cycle(self, point_string, spawn=False):
        """Remove tasks in a cycle from task pool."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        spawn = self._literal_eval('spawn', spawn)
        self.schd.command_queue.put(
            ("remove_tasks", ('%s/*' % point_string,), {"spawn": spawn}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def remove_tasks(self, items, spawn=False):
        """Remove tasks from task pool.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        spawn = self._literal_eval('spawn', spawn)
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
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
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
    def set_stop_after_clock_time(self, datetime_string):
        """Set suite to stop after wallclock time."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        self.schd.command_queue.put(
            ("set_stop_after_clock_time", (datetime_string,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_point(self, point_string):
        """Set suite to stop after cycle point."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        self.schd.command_queue.put(
            ("set_stop_after_point", (point_string,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_after_task(self, task_id):
        """Set suite to stop after an instance of a task."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        self.schd.command_queue.put(
            ("set_stop_after_task", (task_id,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_stop_cleanly(self, kill_active_tasks=False):
        """Set suite to stop cleanly or after kill active tasks."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        kill_active_tasks = self._literal_eval(
            'kill_active_tasks', kill_active_tasks)
        self.schd.command_queue.put(
            ("set_stop_cleanly", (), {"kill_active_tasks": kill_active_tasks}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_verbosity(self, level):
        """Set suite verbosity to new level."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.schd.command_queue.put(("set_verbosity", (level,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def signout(self):
        """Forget client, where possible."""
        uuid = _get_client_info()[4]
        try:
            del self.clients[uuid]
        except KeyError:
            return False
        else:
            LOG.debug(self.LOG_FORGET_TMPL % uuid)
            return True

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def spawn_tasks(self, items):
        """Spawn tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("spawn_tasks", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stop_now(self, terminate=False):
        """Stop suite on event handler completion, or terminate right away."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        terminate = self._literal_eval('terminate', terminate)
        self.schd.command_queue.put(("stop_now", (), {"terminate": terminate}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def take_checkpoints(self, items):
        """Checkpoint current task pool.

        items[0] is the name of the checkpoint.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("take_checkpoints", (items,), {}))
        return (True, 'Command queued')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def trigger_tasks(self, items, back_out=False):
        """Trigger submission of task jobs where possible.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        back_out = self._literal_eval('back_out', back_out)
        if not isinstance(items, list):
            items = [items]
        items = [str(item) for item in items]
        self.schd.command_queue.put(
            ("trigger_tasks", (items,), {"back_out": back_out}))
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
        auth_user, prog_name, user, host, uuid = _get_client_info()
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

    def _check_access_priv_and_report(
            self, required_privilege_level, log_info=True):
        """Check access privilege and log requests with identifying info.

        In debug mode log all requests including task messages. Otherwise log
        all user commands, and just the first info command from each client.

        Return:
            dict: containing the client session

        """
        self._check_access_priv(required_privilege_level)
        command = inspect.currentframe().f_back.f_code.co_name
        auth_user, prog_name, user, host, uuid = _get_client_info()
        priv_level = self._get_priv_level(auth_user)
        LOG.debug(self.__class__.LOG_CONNECT_ALLOWED_TMPL % (
            user, host, prog_name, priv_level, uuid))
        if cylc.flags.debug or uuid not in self.clients and log_info:
            LOG.info(self.__class__.LOG_COMMAND_TMPL % (
                command, user, host, prog_name, uuid))
        self.clients.setdefault(uuid, {})
        self.clients[uuid]['time'] = time()
        self._housekeep()
        return self.clients[uuid]

    def _report_id_requests(self):
        """Report the frequency of identification (scan) requests."""
        self._num_id_requests += 1
        now = time()
        interval = now - self._id_start_time
        if interval > self.CLIENT_ID_REPORT_SECONDS:
            rate = float(self._num_id_requests) / interval
            log = None
            if rate > self.CLIENT_ID_MIN_REPORT_RATE:
                log = LOG.warning
            elif cylc.flags.debug:
                log = LOG.info
            if log:
                log(self.__class__.LOG_IDENTIFY_TMPL % (
                    self._num_id_requests, interval))
            self._id_start_time = now
            self._num_id_requests = 0
        uuid = _get_client_info()[4]
        self.clients.setdefault(uuid, {})
        self.clients[uuid]['time'] = now
        self._housekeep()

    def _get_priv_level(self, auth_user):
        """Get the privilege level for this authenticated user."""
        if auth_user == "cylc":
            return PRIVILEGE_LEVELS[-1]
        return self.schd.config.cfg['cylc']['authentication']['public']

    def _housekeep(self):
        """Forget inactive clients."""
        for uuid, client_info in self.clients.copy().items():
            if time() - client_info['time'] > self.CLIENT_FORGET_SEC:
                try:
                    del self.clients[uuid]
                except KeyError:
                    pass
                LOG.debug(self.LOG_FORGET_TMPL % uuid)

    @staticmethod
    def _literal_eval(key, value, default=None):
        """Wrap ast.literal_eval if value is basestring.

        On SyntaxError or ValueError, return default is default is not None.
        Otherwise, raise HTTPError 400.
        """
        if isinstance(value, basestring):
            try:
                return ast.literal_eval(value)
            except (SyntaxError, ValueError):
                if default is not None:
                    return default
                raise cherrypy.HTTPError(
                    400, r'Bad argument value: %s=%s' % (key, value))
        else:
            return value


def _get_client_info():
    """Return information about the most recent cherrypy request, if any."""
    auth_user = cherrypy.request.login
    info = cherrypy.request.headers
    origin_string = info.get("User-Agent", "")
    origin_props = {}
    if origin_string:
        try:
            origin_props = dict(
                [_.split("/", 1) for _ in origin_string.split()]
            )
        except ValueError:
            pass
    prog_name = origin_props.get("prog_name", "Unknown")
    uuid = origin_props.get("uuid", uuid4())
    if info.get("From") and "@" in info["From"]:
        user, host = info["From"].split("@")
    else:
        user, host = ("Unknown", "Unknown")
    return auth_user, prog_name, user, host, uuid

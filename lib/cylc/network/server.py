#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Server for suite runtime API."""

import getpass
import re
from queue import Queue
from time import sleep
from threading import Thread

import zmq

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.network import Priv, encrypt, decrypt, get_secret
from cylc.suite_status import (
    KEY_META, KEY_NAME, KEY_OWNER, KEY_STATES,
    KEY_TASKS_BY_STATE, KEY_UPDATE_TIME, KEY_VERSION)
from cylc.version import CYLC_VERSION
from cylc.wallclock import RE_DATE_TIME_FORMAT_EXTENDED


class ZMQServer(object):
    """Initiate the REP part of a ZMQ REQ-REP pair.

    This class contains the logic for the ZMQ message interface and client -
    server communication.

    NOTE: Security to be provided via the encode / decode interface.

    Args:
        encode_method (function): Translates outgoing messages into strings
            to be sent over the network. ``encode_method(json, secret) -> str``
        decode_method (function): Translates incoming message strings into
            digestible data. ``encode_method(str, secret) -> dict``
        secret_method (function): Return the secret for use with the
            encode/decode methods. Called for each encode / decode.

    Usage:
        * Define endpoints using the ``expose`` decorator.
        * Call endpoints using the function name.

    Message interface:
        * Accepts requests of the format: {"command": CMD, "args": {...}}
        * Returns responses of the format: {"data": {...}}
        * Returns error in the format: {"error": {"message": MSG}}

    """

    RECV_TIMEOUT = 1
    """Max time the ZMQServer will wait for an incomming message in seconds.

    We use a timeout here so as to give the _listener a chance to respond to
    requests (i.e. stop) from its spawner (the scheduler).

    The alternative would be to spin up a client and send a message to the
    server, this way seems safer.

    """

    def __init__(self, encode_method, decode_method, secret_method):
        self.port = None
        self.socket = None
        self.endpoints = None
        self.thread = None
        self.queue = None
        self.encode = encode_method
        self.decode = decode_method
        self.secret = secret_method

    def start(self, ports):
        """Start the server running

        Args:
            ports (iterable): Generator of ports (int) to choose from.
                The lowest available port will be chosen.

        """
        # create socket
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.RCVTIMEO = int(self.RECV_TIMEOUT) * 1000

        # pick port
        for port in ports:
            try:
                self.socket.bind('tcp://*:%d' % port)
            except zmq.error.ZMQError:
                pass
            else:
                self.port = port
                break
        else:
            raise Exception('No room at the inn, all ports occupied.')

        # start accepting requests
        self.register_endpoints()

        self.queue = Queue()
        # TODO: this in asyncio? Requires the Cylc main loop in ascyncio first
        self.thread = Thread(target=self._listener)
        self.thread.start()

    def stop(self):
        """Finish serving the current request then stop the server."""
        LOG.debug('stopping zmq server...')
        self.queue.put('STOP')
        self.thread.join()  # wait for the listener to return
        LOG.debug('...stopped')

    def register_endpoints(self):
        """Register all exposed methods."""
        self.endpoints = {name: obj
                          for name, obj in self.__class__.__dict__.items()
                          if hasattr(obj, 'exposed')}

    def _listener(self):
        """The server main loop, listen for and serve requests."""
        while True:
            # process any commands passed to the listner by its parent process
            if self.queue.qsize():
                command = self.queue.get()
                if command == 'STOP':
                    break
                else:
                    raise ValueError('Unknown command "%s"' % command)

            try:
                # wait RECV_TIMEOUT for a message
                msg = self.socket.recv_string()
            except zmq.error.Again:
                # timeout, continue with the loop, this allows the listener
                # thread to stop
                continue

            # attempt to decode the message, authenticating the user in the
            # process
            try:
                message = self.decode(msg, self.secret())
                LOG.debug('zmq:recv %s', message)
            except Exception as exc:  # purposefully catch generic exception
                # failed to decode message, possibly resulting from failed
                # authentication
                response = self.encode(
                    {'error': {'message': str(exc)}}, self.secret())
            else:
                # success case - serve the request
                res = self._receiver(message)
                response = self.encode(res, self.secret())
                LOG.debug('zmq:send %s', res)

            # send back the response
            self.socket.send_string(response)
            sleep(0)  # yield control to other threads

    def _receiver(self, message):
        """Wrap incoming messages and dispatch them to exposed methods."""
        # determine the server method to call
        try:
            method = getattr(self, message['command'])
            args = message['args']
            args.update({'user': message['user']})
            if 'meta' in message:
                args['meta'] = message['meta']
        except KeyError:
            # malformed message
            return {'error': {
                'message': 'Request missing required field(s).'}}
        except AttributeError:
            # no exposed method by that name
            return {'error': {
                'message': 'No method by the name "%s"' % message['command']}}

        # generate response
        try:
            response = method(**args)
        except Exception as exc:
            # includes incorrect arguments (TypeError)
            LOG.error(exc)  # note the error server side
            import traceback
            return {'error': {
                'message': str(exc), 'traceback': traceback.format_exc()}}

        return {'data': response}

    @staticmethod
    def expose(func=None):
        """Expose a method on the sever."""
        func.exposed = True
        return func


def authorise(req_priv_level):
    """Add authorisation to an endpoint.

    This decorator extracts the `user` field from the incoming message to
    determine the client's privilege level.

    Args:
        req_priv_level (cylc.network.Priv): A privilege level for the method.

    """
    def wrapper(fcn):
        def _authorise(self, *args, user='?', meta=None, **kwargs):
            host = meta.get('host', '?')
            prog = meta.get('prog', '?')

            usr_priv_level = self.get_priv_level(user)
            if usr_priv_level < req_priv_level:
                LOG.info(
                    "[client-connect] DENIED (privilege '%s' < '%s') %s@%s:%s",
                    usr_priv_level, req_priv_level, user, host, prog)
                raise Exception('Authorisation failure')
            LOG.info(
                '[client-command] %s %s@%s:%s', fcn.__name__, user, host, prog)
            return fcn(self, *args, **kwargs)
        return _authorise
    return wrapper


class SuiteRuntimeServer(ZMQServer):
    """Suite runtime service API facade exposed via zmq.

    This class contains the cylc endpoints.

    Note the following argument names are protected:

    user
        The authenticated user (determined server side)
    host
        The client host (if provided by client) - non trustworthy
    prog
        The client program name (if provided by client) - non trustworthy

    """

    API = 4  # cylc API version

    def __init__(self, schd):
        ZMQServer.__init__(
            self,
            encrypt,
            decrypt,
            lambda: get_secret(schd.suite)
        )
        self.schd = schd
        self.public_priv = None  # update in get_public_priv()

    def get_public_priv(self):
        """Return the public privilege level of this suite."""
        if self.schd.config.cfg['cylc']['authentication']['public']:
            return Priv.parse(
                self.schd.config.cfg['cylc']['authentication']['public'])
        return Priv.parse(glbl_cfg().get(['authentication', 'public']))

    def get_priv_level(self, user):
        """Return the privilege level for the given user for this suite."""
        if user == getpass.getuser():
            return Priv.CONTROL
        if self.public_priv is None:
            # cannot do this on initialisation as the suite configuration has
            # not yet been parsed
            self.public_priv = self.get_public_priv()
        return self.public_priv

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
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
        return self.schd.task_events_mgr.broadcast_mgr.clear_broadcast(
            point_strings, namespaces, cancel_settings)

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def dry_run_tasks(self, items, check_syntax=True):
        """Prepare job file for a task.

        items[0] is an identifier for matching a task proxy.
        """
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(('dry_run_tasks', (items,),
                                    {'check_syntax': check_syntax}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def expire_broadcast(self, cutoff=None):
        """Clear all settings targeting cycle points earlier than cutoff."""
        return self.schd.task_events_mgr.broadcast_mgr.expire_broadcast(cutoff)

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_broadcast(self, task_id=None):
        """Retrieve all broadcast variables that target a given task ID."""
        return self.schd.task_events_mgr.broadcast_mgr.get_broadcast(task_id)

    @authorise(Priv.IDENTITY)
    @ZMQServer.expose
    def get_cylc_version(self):
        """Return the cylc version running this suite."""
        return CYLC_VERSION

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_graph_raw(self, start_point_string, stop_point_string,
                      group_nodes=None, ungroup_nodes=None,
                      ungroup_recursive=False, group_all=False,
                      ungroup_all=False):
        """Return raw suite graph."""
        # Ensure that a "None" str is converted to the None value.
        if stop_point_string is not None:
            stop_point_string = str(stop_point_string)
        return self.schd.info_get_graph_raw(
            start_point_string, stop_point_string,
            group_nodes=group_nodes,
            ungroup_nodes=ungroup_nodes,
            ungroup_recursive=ungroup_recursive,
            group_all=group_all,
            ungroup_all=ungroup_all)

    @authorise(Priv.DESCRIPTION)
    @ZMQServer.expose
    def get_suite_info(self):
        """Return a dict containing the suite title and description."""
        return self.schd.info_get_suite_info()

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_suite_state_summary(self):
        """Return the global, task, and family summary data structures."""
        return self.schd.info_get_suite_state_summary()

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_task_info(self, names):
        """Return info of a task."""
        if not isinstance(names, list):
            names = [names]
        return self.schd.info_get_task_info(names)

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_task_jobfile_path(self, task_id):
        """Return task job file path."""
        return self.schd.info_get_task_jobfile_path(task_id)

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_task_requisites(self, items=None, list_prereqs=False):
        """Return prerequisites of a task."""
        if not isinstance(items, list):
            items = [items]
        return self.schd.info_get_task_requisites(
            items, list_prereqs=(list_prereqs in [True, 'True']))

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def hold_after_point_string(self, point_string):
        """Set hold point of suite."""
        self.schd.command_queue.put(
            ("hold_after_point_string", (point_string,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def hold_suite(self):
        """Hold the suite."""
        self.schd.command_queue.put(("hold_suite", (), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def hold_tasks(self, items):
        """Hold tasks.

        items is a list of identifiers for matching task proxies.
        """
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("hold_tasks", (items,), {}))
        return (True, 'Command queued')

    @authorise(Priv.IDENTITY)
    @ZMQServer.expose
    def identify(self):
        return {
            KEY_NAME: self.schd.suite,
            KEY_OWNER: self.schd.owner,
            KEY_VERSION: CYLC_VERSION
        }

    @authorise(Priv.DESCRIPTION)
    @ZMQServer.expose
    def describe(self):
        return {KEY_META: self.schd.config.cfg[KEY_META]}

    @authorise(Priv.STATE_TOTALS)
    @ZMQServer.expose
    def state_totals(self):
        return {
            KEY_UPDATE_TIME: self.schd.state_summary_mgr.update_time,
            KEY_STATES: self.schd.state_summary_mgr.get_state_totals(),
            KEY_TASKS_BY_STATE:
                self.schd.state_summary_mgr.get_tasks_by_state()
        }

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def insert_tasks(self, items, stop_point_string=None, no_check=False):
        """Insert task proxies.

        items is a list of identifiers of (families of) task instances.
        """
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

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def kill_tasks(self, items):
        """Kill task jobs.

        items is a list of identifiers for matching task proxies.
        """
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("kill_tasks", (items,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def nudge(self):
        """Tell suite to try task processing."""
        self.schd.command_queue.put(("nudge", (), {}))
        return (True, 'Command queued')

    @authorise(Priv.IDENTITY)
    @ZMQServer.expose
    def ping_suite(self):
        """Return True."""
        return True

    @authorise(Priv.READ)
    @ZMQServer.expose
    def ping_task(self, task_id, exists_only=False):
        """Return True if task_id exists (and running)."""
        return self.schd.info_ping_task(task_id, exists_only=exists_only)

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def poll_tasks(self, items=None, poll_succ=False):
        """Poll task jobs.

        items is a list of identifiers for matching task proxies.
        """
        if items is not None and not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(
            ("poll_tasks", (items,),
                {"poll_succ": poll_succ in ['True', True]}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def put_broadcast(
            self, point_strings=None, namespaces=None, settings=None):
        """Add new broadcast settings (server side interface).

        Return a tuple (modified_settings, bad_options) where:
          modified_settings is list of modified settings in the form:
            [("20200202", "foo", {"command scripting": "true"}, ...]
          bad_options is as described in the docstring for self.clear().
        """
        return self.schd.task_events_mgr.broadcast_mgr.put_broadcast(
            point_strings, namespaces, settings)

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def put_ext_trigger(self, event_message, event_id):
        """Server-side external event trigger interface."""
        self.schd.ext_trigger_queue.put((event_message, event_id))
        return (True, 'Event queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def put_messages(self, task_job=None, event_time=None, messages=None):
        """Put task messages in queue for processing later by the main loop.

        Arguments:
            task_job (str): Task job in the form "CYCLE/TASK_NAME/SUBMIT_NUM".
            event_time (str): Event time as string.
            messages (list): List in the form [[severity, message], ...].
        """
        for severity, message in messages:
            self.schd.message_queue.put(
                (task_job, event_time, severity, message))
        return (True, 'Messages queued: %d' % len(messages))

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def reload_suite(self):
        """Tell suite to reload the suite definition."""
        self.schd.command_queue.put(("reload_suite", (), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def release_suite(self):
        """Unhold suite."""
        self.schd.command_queue.put(("release_suite", (), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def release_tasks(self, items):
        """Unhold tasks.

        items is a list of identifiers for matching task proxies.
        """
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("release_tasks", (items,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def remove_tasks(self, items, spawn=False):
        """Remove tasks from task pool.

        items is a list of identifiers for matching task proxies.
        """
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(
            ("remove_tasks", (items,), {"spawn": spawn}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def reset_task_states(self, items, state=None, outputs=None):
        """Reset statuses tasks.

        items is a list of identifiers for matching task proxies.
        """
        if not isinstance(items, list):
            items = [items]
        if outputs and not isinstance(outputs, list):
            outputs = [outputs]
        self.schd.command_queue.put((
            "reset_task_states",
            (items,), {"state": state, "outputs": outputs}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def set_stop_after_clock_time(self, datetime_string):
        """Set suite to stop after wallclock time."""
        self.schd.command_queue.put(
            ("set_stop_after_clock_time", (datetime_string,), {}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def set_stop_after_point(self, point_string):
        """Set suite to stop after cycle point."""
        self.schd.command_queue.put(
            ("set_stop_after_point", (point_string,), {}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def set_stop_after_task(self, task_id):
        """Set suite to stop after an instance of a task."""
        self.schd.command_queue.put(
            ("set_stop_after_task", (task_id,), {}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def set_stop_cleanly(self, kill_active_tasks=False):
        """Set suite to stop cleanly or after kill active tasks."""
        self.schd.command_queue.put(
            ("set_stop_cleanly", (), {"kill_active_tasks": kill_active_tasks}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def set_verbosity(self, level):
        """Set suite verbosity to new level."""
        self.schd.command_queue.put(("set_verbosity", (level,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def spawn_tasks(self, items):
        """Spawn tasks.

        items is a list of identifiers for matching task proxies.
        """
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("spawn_tasks", (items,), {}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def stop_now(self, terminate=False):
        """Stop suite on event handler completion, or terminate right away."""
        self.schd.command_queue.put(("stop_now", (), {"terminate": terminate}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def take_checkpoints(self, items):
        """Checkpoint current task pool.

        items[0] is the name of the checkpoint.
        """
        if not isinstance(items, list):
            items = [items]
        self.schd.command_queue.put(("take_checkpoints", (items,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def trigger_tasks(self, items, back_out=False):
        """Trigger submission of task jobs where possible.

        items is a list of identifiers for matching task proxies.
        """
        if not isinstance(items, list):
            items = [items]
        items = [str(item) for item in items]
        self.schd.command_queue.put(
            ("trigger_tasks", (items,), {"back_out": back_out}))
        return (True, 'Command queued')

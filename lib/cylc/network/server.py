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

from functools import wraps
import getpass
from queue import Queue
from textwrap import dedent
from time import sleep
from threading import Thread

import zmq

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.network import Priv, encrypt, decrypt, get_secret
from cylc.suite_status import (
    KEY_META, KEY_NAME, KEY_OWNER, KEY_STATES,
    KEY_TASKS_BY_STATE, KEY_UPDATE_TIME, KEY_VERSION)
from cylc import __version__ as CYLC_VERSION


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
    """Max time the ZMQServer will wait for an incoming message in seconds.

    We use a timeout here so as to give the _listener a chance to respond to
    requests (i.e. stop) from its spawner (the scheduler).

    The alternative would be to spin up a client and send a message to the
    server, this way seems safer.

    """

    def __init__(self, encode_method, decode_method, secret_method):
        self.port = None
        self.context = zmq.Context()
        self.socket = None
        self.endpoints = None
        self.thread = None
        self.queue = None
        self.encode = encode_method
        self.decode = decode_method
        self.secret = secret_method

    def start(self, min_port, max_port):
        """Start the server running.

        Will use a port range provided to select random ports.

        Args:
            min_port (int): minimum socket port number
            max_port (int): maximum socket port number
        """
        # create socket
        self.socket = self.context.socket(zmq.REP)
        self.socket.RCVTIMEO = int(self.RECV_TIMEOUT) * 1000

        self.port = self.socket.bind_to_random_port(
            'tcp://*', min_port, max_port)

        # start accepting requests
        self.register_endpoints()

        self.queue = Queue()
        # TODO: this in asyncio? Requires the Cylc main loop in asyncio first
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
            # process any commands passed to the listener by its parent process
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
            except Exception as exc:  # purposefully catch generic exception
                # failed to decode message, possibly resulting from failed
                # authentication
                import traceback
                return {'error': {
                    'message': str(exc), 'traceback': traceback.format_exc()}}
            else:
                # success case - serve the request
                LOG.debug('zmq:recv %s', message)
                res = self._receiver(message)
                response = self.encode(res, self.secret())
                LOG.debug('zmq:send %s', res)

            # send back the response
            self.socket.send_string(response)
            sleep(0)  # yield control to other threads

    def _receiver(self, message):
        """Wrap incoming messages and dispatch them to exposed methods.

        Args:
            message (dict): message contents
        """
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
            LOG.exception(exc)  # note the error server side
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

    Wrapped function args:
        user
            The authenticated user (determined server side)
        host
            The client host (if provided by client) - non trustworthy
        prog
            The client program name (if provided by client) - non trustworthy

    """
    def wrapper(fcn):
        @wraps(fcn)  # preserve args and docstrings
        def _authorise(self, *args, user='?', meta=None, **kwargs):
            if not meta:
                meta = {}
            host = meta.get('host', '?')
            prog = meta.get('prog', '?')

            usr_priv_level = self._get_priv_level(user)
            if usr_priv_level < req_priv_level:
                LOG.warn(
                    "[client-connect] DENIED (privilege '%s' < '%s') %s@%s:%s",
                    usr_priv_level, req_priv_level, user, host, prog)
                raise Exception('Authorisation failure')
            LOG.info(
                '[client-command] %s %s@%s:%s', fcn.__name__, user, host, prog)
            return fcn(self, *args, **kwargs)
        _authorise.__doc__ += (  # add auth level to docstring
            'Authentication:\n%s:py:obj:`cylc.network.%s`\n' % (
                ' ' * 12, req_priv_level))
        return _authorise
    return wrapper


class SuiteRuntimeServer(ZMQServer):
    """Suite runtime service API facade exposed via zmq.

    This class contains the Cylc endpoints.

    Common Arguments:
        Arguments which are shared between multiple commands.

        .. _task identifier:

        task identifier (str):
            A task identifier in the format ``task.cycle-point``
            e.g. ``foo.1`` or ``bar.20000101T0000Z``.

        .. _task globs:

        task globs (list):
            A list of strings in the format
            ``name[.cycle_point][:task_state]`` where ``name`` could be a
            task or family name.

             Glob-like patterns may be used to match multiple items e.g.

             ``*``
                Matches everything.
             ``*.1``
                Matches everything in cycle ``1``.
             ``*.*:failed``
                Matches all failed tasks.

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

    def _get_public_priv(self):
        """Return the public privilege level of this suite."""
        if self.schd.config.cfg['cylc']['authentication']['public']:
            return Priv.parse(
                self.schd.config.cfg['cylc']['authentication']['public'])
        return Priv.parse(glbl_cfg().get(['authentication', 'public']))

    def _get_priv_level(self, user):
        """Return the privilege level for the given user for this suite."""
        if user == getpass.getuser():
            return Priv.CONTROL
        if self.public_priv is None:
            # cannot do this on initialisation as the suite configuration has
            # not yet been parsed
            self.public_priv = self._get_public_priv()
        return self.public_priv

    @authorise(Priv.IDENTITY)
    @ZMQServer.expose
    def api(self, endpoint=None):
        """Return information about this API.

        Returns a list of callable endpoints.

        Args:
            endpoint (str, optional):
                If specified the documentation for the endpoint
                will be returned instead.

        Returns:
            list/str: List of endpoints or string documentation of the
            requested endpoint.

        """
        if not endpoint:
            return [
                method for method in dir(self)
                if getattr(getattr(self, method), 'exposed', False)
            ]

        try:
            method = getattr(self, endpoint)
        except AttributeError:
            return 'No method by name "%s"' % endpoint
        if method.exposed:
            head, tail = method.__doc__.split('\n', 1)
            tail = dedent(tail)
            return '%s\n%s' % (head, tail)
        return 'No method by name "%s"' % endpoint

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def clear_broadcast(
            self, point_strings=None, namespaces=None, cancel_settings=None):
        """Clear settings globally, or for listed namespaces and/or points.

        Args:
            point_strings (list, optional):
                List of point strings for this operation to apply to or
                ``None`` to apply to all cycle points.
            namespaces (list, optional):
                List of namespace string (task / family names) for this
                operation to apply to or ``None`` to apply to all namespaces.
            cancel_settings (list, optional):
                List of broadcast keys to cancel.

        Returns:
            tuple: (modified_settings, bad_options)

                modified_settings
                   similar to the return value of the "put" method, but for
                   removed settings.
                bad_options
                   A dict in the form:
                   ``{"point_strings": ["20020202", ..."], ...}``.
                   The dict is only populated if there are options not
                   associated with previous broadcasts. The keys can be:

                   * point_strings: a list of bad point strings.
                   * namespaces: a list of bad namespaces.
                   * cancel: a list of tuples. Each tuple contains the keys of
                     a bad setting.

        """
        return self.schd.task_events_mgr.broadcast_mgr.clear_broadcast(
            point_strings, namespaces, cancel_settings)

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def dry_run_tasks(self, task_globs, check_syntax=True):
        """Prepare job file for a task.

        Args:
            task_globs (list): List of identifiers, see `task globs`_
            check_syntax (bool, optional): Check shell syntax.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(('dry_run_tasks', (task_globs,),
                                    {'check_syntax': check_syntax}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def expire_broadcast(self, cutoff=None):
        """Clear all settings targeting cycle points earlier than cutoff.

        Args:
            cutoff (str, optional):
                Cycle point, broadcasts earlier than but not inclusive of the
                cutoff will be canceled.

        """
        return self.schd.task_events_mgr.broadcast_mgr.expire_broadcast(cutoff)

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_broadcast(self, task_id=None):
        """Retrieve all broadcast variables that target a given task ID.

        Args:
            task_id (str, optional): A `task identifier`_

        Returns:
            dict: all broadcast variables that target the given task ID.

        """
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
        """Return a textural representation of the suite graph.

        .. warning::

           The grouping options:

           * ``group_nodes``
           * ``ungroup_nodes``
           * ``group_all``
           * ``ungroup_all``

           Are mutually exclusive.

        Args:
            start_point_string (str):
                Cycle point as a string to define the window of view of the
                suite graph.
            stop_point_string (str):
                Cycle point as a string to define the window of view of the
                suite graph.
            group_nodes (list, optional):
                List of (graph nodes) family names to group (collapse according
                to inheritance) in the output graph.
            ungroup_nodes (list, optional):
                List of (graph nodes) family names to ungroup (expand according
                to inheritance) in the output graph.
            ungroup_recursive (bool, optional):
                Recursively ungroup families.
            group_all (bool, optional):
                Group all families (collapse according to inheritance).
            ungroup_all (bool, optional):
                Ungroup all families (expand according to inheritance).

        Returns:
            list: [left, right, None, is_suicide, condition]

            left (str):
                `Task identifier <task identifier>` for the dependency of
                an edge.
            right (str):
                `Task identifier <task identifier>` for the dependant task
                of an edge.
            is_suicide (bool):
                True if edge represents a suicide trigger.
            condition:
                Conditional expression if edge represents a conditional trigger
                else ``None``.

        """
        # Ensure that a "None" str is converted to the None value.
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
        """Return a dictionary containing the suite title and description.

        Returns:
            dict: The `[meta]` section of a suite configuration

        """
        return self.schd.info_get_suite_info()

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_suite_state_summary(self):
        """Return the global, task, and family summary data summaries.

        Returns:
            tuple: (global_summary, task_summary, family_summary)

            global_summary (dict):
                Contains suite status items e.g. ``last_updated``.
            task_summary (dict):
                A dictionary of `task identifiers <task identifier>`_
                in the format ``{task_id: {...}, ...}``.
            family_summary (dict):
                Contains task family information in the format
                ``{family_id: {...}, ...}``.

        """
        return self.schd.info_get_suite_state_summary()

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_task_info(self, names):
        """Return the configurations for the provided tasks.

        Args:
            names (list): A list of task names to request information for.

        Returns:
            dict: Dictionary in the format ``{'task': {...}, ...}``

        """
        return self.schd.info_get_task_info(names)

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_task_jobfile_path(self, task_id):
        """Return task job file path.

        Args:
            task_id: A `task identifier`_

        Returns:
            str: The jobfile path.

        """
        return self.schd.info_get_task_jobfile_path(task_id)

    @authorise(Priv.READ)
    @ZMQServer.expose
    def get_task_requisites(self, task_globs=None, list_prereqs=False):
        """Return prerequisites of a task.

        Args:
            task_globs (list, optional):
                List of identifiers, see `task globs`_
            list_prereqs (bool): whether to include the prerequisites in
                the results or not.

        Returns:
            list: Dictionary of `task identifiers <task identifier>`_
            in the format ``{task_id: { ... }, ...}``.

        """
        return self.schd.info_get_task_requisites(
            task_globs, list_prereqs=list_prereqs)

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def hold_after_point_string(self, point_string):
        """Set hold point of suite.

        Args:
            point_string (str): The cycle point to hold the suite *after.*

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("hold_after_point_string", (point_string,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def hold_suite(self):
        """Hold the suite.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("hold_suite", (), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def hold_tasks(self, task_globs):
        """Hold tasks.

        Args:
            task_globs (list): List of identifiers, see `task globs`_

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("hold_tasks", (task_globs,), {}))
        return (True, 'Command queued')

    @authorise(Priv.IDENTITY)
    @ZMQServer.expose
    def identify(self):
        """Return basic information about the suite.

        Returns:
            dict: Dictionary containing the keys

            cylc.suite_status.KEY_NAME
               The suite name.
            cylc.suite_status.KEY_OWNER
               The user account the suite is running under.
            cylc.suite_status.KEY_VERSION
               The Cylc version the suite is running with.

        """
        return {
            KEY_NAME: self.schd.suite,
            KEY_OWNER: self.schd.owner,
            KEY_VERSION: CYLC_VERSION
        }

    @authorise(Priv.DESCRIPTION)
    @ZMQServer.expose
    def describe(self):
        """Return the suite metadata.]

        Returns:
            dict: ``{cylc.suite_status: { ... }}``

        """
        return {KEY_META: self.schd.config.cfg[KEY_META]}

    @authorise(Priv.STATE_TOTALS)
    @ZMQServer.expose
    def state_totals(self):
        """Returns counts of the task states present in the suite.

        Returns:
            dict: Dictionary with the keys:

            cylc.suite_status.KEY_UPDATE_TIME
               ISO8601 timestamp of when this data snapshot was made.
            cylc.suite_status.KEY_STATES
               Tuple of the form ``(state_count_totals, state_count_cycles)``

               state_count_totals (dict):
                  Dictionary of the form ``{task_state: task_count}``.
               state_count_cycles (dict):
                  Dictionary of the form ``{cycle_point: task_count}``.
            cylc.suite_status.KEY_TASKS_BY_STATE
               Dictionary in the form
               ``{state: [(most_recent_time_string, task_name, point_string),``
               ``...]}``.

        """
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

        Args:
            items (list):
                A list of `task globs`_ (strings) which *cannot* contain
                any glob characters (``*``).
            stop_point_string (str, optional):
                Optional hold/stop cycle point for inserted task.
            no_check (bool, optional):
                Add task even if the provided cycle point is not valid
                for the given task.
        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put((
            "insert_tasks",
            (items,),
            {"stop_point_string": stop_point_string, "no_check": no_check}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def kill_tasks(self, task_globs):
        """Kill task jobs.

        Args:
            task_globs (list): List of identifiers, see `task globs`_

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("kill_tasks", (task_globs,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def nudge(self):
        """Tell suite to try task processing.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("nudge", (), {}))
        return (True, 'Command queued')

    @authorise(Priv.IDENTITY)
    @ZMQServer.expose
    def ping_suite(self):
        """Return True.

        This serves as a basic network comms tests.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        return True

    @authorise(Priv.READ)
    @ZMQServer.expose
    def ping_task(self, task_id, exists_only=False):
        """Return True if task_id exists (and is running).

        Args:
            task_id:
                A `task identifier`_
            exists_only (bool, optional):
                If True only test that the task exists, if False check both
                that the task exists and that it is running.

        Returns:
            tuple: (outcome, message)

            outcome (bool):
                True if task exists (and is running).
            message (str):
                A string describing the outcome / state of the task.

        """
        return self.schd.info_ping_task(task_id, exists_only=exists_only)

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def poll_tasks(self, task_globs=None, poll_succ=False):
        """Request the suite to poll task jobs.

        Args:
            task_globs (list, optional):
                List of identifiers, see `task globs`_
            poll_succ (bool, optional):
                Allow polling of remote tasks if True.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("poll_tasks", (task_globs,), {"poll_succ": poll_succ}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def put_broadcast(
            self, point_strings=None, namespaces=None, settings=None):
        """Add new broadcast settings (server side interface).

        Args:
            point_strings (list, optional):
                List of point strings for this operation to apply to or
                ``None`` to apply to all cycle points.
            namespaces (list, optional):
                List of namespace string (task / family names) for this
                operation to apply to or ``None`` to apply to all namespaces.
            settings (list, optional):
                List of strings in the format ``key=value`` where ``key`` is a
                Cylc configuration including section names e.g.
                ``[section][subsection]item``.

        Returns:
            tuple: (modified_settings, bad_options)

                modified_settings
                   similar to the return value of the "put" method, but for
                   removed settings.
                bad_options
                   A dict in the form:
                   ``{"point_strings": ["20020202", ..."], ...}``.
                   The dict is only populated if there are options not
                   associated with previous broadcasts. The keys can be:

                   * point_strings: a list of bad point strings.
                   * namespaces: a list of bad namespaces.
                   * cancel: a list of tuples. Each tuple contains the keys of
                     a bad setting.

        """
        return self.schd.task_events_mgr.broadcast_mgr.put_broadcast(
            point_strings, namespaces, settings)

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def put_ext_trigger(self, event_message, event_id):
        """Server-side external event trigger interface.

        Args:
            event_message (str): The external trigger message.
            event_id (str): The unique trigger ID.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.ext_trigger_queue.put((event_message, event_id))
        return (True, 'Event queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def put_messages(self, task_job=None, event_time=None, messages=None):
        """Put task messages in queue for processing later by the main loop.

        Arguments:
            task_job (str, optional):
                Task job in the format ``CYCLE/TASK_NAME/SUBMIT_NUM``.
            event_time (str, optional):
                Event time as an ISO8601 string.
            messages (list, optional):
                List in the format ``[[severity, message], ...]``.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        #  TODO: standardise the task_job interface to one of the other
        #        systems
        for severity, message in messages:
            self.schd.message_queue.put(
                (task_job, event_time, severity, message))
        return (True, 'Messages queued: %d' % len(messages))

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def reload_suite(self):
        """Tell suite to reload the suite definition.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("reload_suite", (), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def release_suite(self):
        """Unhold suite.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("release_suite", (), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def release_tasks(self, task_globs):
        """Unhold tasks.

        Args:
            task_globs (list): List of identifiers, see `task globs`_

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("release_tasks", (task_globs,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def remove_tasks(self, task_globs, spawn=False):
        """Remove tasks from task pool.

        Args:
            task_globs (list):
                List of identifiers, see `task globs`_
            spawn (bool, optional):
                If True ensure task has spawned before removal.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("remove_tasks", (task_globs,), {"spawn": spawn}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def reset_task_states(self, task_globs, state=None, outputs=None):
        """Reset statuses tasks.

        Args:
            task_globs (list):
                List of identifiers, see `task globs`_
            state (str, optional):
                Task state to reset task to.
                See ``cylc.task_state.TASK_STATUSES_CAN_RESET_TO``.
            outputs (list, optional):
                Find task output by message string or trigger string
                set complete or incomplete with !OUTPUT
                ``*`` to set all complete, ``!*`` to set all incomplete.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put((
            "reset_task_states",
            (task_globs,), {"state": state, "outputs": outputs}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def set_stop_after_clock_time(self, datetime_string):
        """Set suite to stop after wallclock time.

        Args:
            datetime_string (str):
                An ISO8601 formatted date-time of the wallclock
                (real-world as opposed to simulation) time
                to stop the suite after.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("set_stop_after_clock_time", (datetime_string,), {}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def set_stop_after_point(self, point_string):
        """Set suite to stop after cycle point.

        Args:
            point_string (str):
                The cycle point to stop the suite after.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("set_stop_after_point", (point_string,), {}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def set_stop_after_task(self, task_id):
        """Set suite to stop after an instance of a task.

        Args:
            task_id (str): A `task identifier`_

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("set_stop_after_task", (task_id,), {}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def set_stop_cleanly(self, kill_active_tasks=False):
        """Set suite to stop cleanly or after kill active tasks.

        The suite will wait for all active (running, submitted) tasks
        to complete before stopping.

        Args:
            kill_active_tasks (bool, optional):
                If True the suite will attempt to kill any active
                (running, submitted) tasks

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("set_stop_cleanly", (), {"kill_active_tasks": kill_active_tasks}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def set_verbosity(self, level):
        """Set suite verbosity to new level (for suite logs).

        Args:
            level (str): A logging level e.g. ``INFO`` or ``ERROR``.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("set_verbosity", (level,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def spawn_tasks(self, task_globs):
        """Spawn tasks.

        Args:
            task_globs (list): List of identifiers, see `task globs`_

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("spawn_tasks", (task_globs,), {}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @ZMQServer.expose
    def stop_now(self, terminate=False):
        """Stop suite on event handler completion, or terminate right away.

        Args:
            terminate (bool, optional):
                If False Cylc will run event handlers, if True it will not.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("stop_now", (), {"terminate": terminate}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def take_checkpoints(self, name):
        """Checkpoint current task pool.

        Args:
            name (str): The checkpoint name

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("take_checkpoints", (name,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @ZMQServer.expose
    def trigger_tasks(self, task_globs, back_out=False):
        """Trigger submission of task jobs where possible.

        Args:
            task_globs (list):
                List of identifiers, see `task globs`_
            back_out (bool, optional):
                Abort e.g. in the event of a rejected trigger-edit.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("trigger_tasks", (task_globs,), {"back_out": back_out}))
        return (True, 'Command queued')

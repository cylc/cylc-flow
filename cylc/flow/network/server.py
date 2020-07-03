# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
from queue import Queue
from textwrap import dedent
from time import sleep

from graphql.execution.executors.asyncio import AsyncioExecutor
import zmq

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.network import encode_, decode_, ZMQSocketBase
from cylc.flow.network.authorisation import Priv, authorise
from cylc.flow.network.graphql import (
    CylcGraphQLBackend, IgnoreFieldMiddleware, instantiate_middleware
)
from cylc.flow.network.resolvers import Resolvers
from cylc.flow.network.schema import schema
from cylc.flow.suite_status import (
    KEY_META, KEY_NAME, KEY_OWNER, KEY_STATES,
    KEY_TASKS_BY_STATE, KEY_UPDATE_TIME, KEY_VERSION
)
from cylc.flow.data_store_mgr import DELTAS_MAP
from cylc.flow.data_messages_pb2 import PbEntireWorkflow
from cylc.flow import __version__ as CYLC_VERSION

# maps server methods to the protobuf message (for client/UIS import)
PB_METHOD_MAP = {
    'pb_entire_workflow': PbEntireWorkflow,
    'pb_data_elements': DELTAS_MAP
}


def expose(func=None):
    """Expose a method on the sever."""
    func.exposed = True
    return func


def filter_none(dictionary):
    """Filter out `None` items from a dictionary:

    Examples:
        >>> filter_none({
        ...     'a': 0,
        ...     'b': '',
        ...     'c': None
        ... })
        {'a': 0, 'b': ''}

    """
    return {
        key: value
        for key, value in dictionary.items()
        if value is not None
    }


class SuiteRuntimeServer(ZMQSocketBase):
    """Suite runtime service API facade exposed via zmq.

    This class contains the Cylc endpoints.

    Args:
        schd (object): The parent object instantiating the server. In
            this case, the workflow scheduler.
        context (object): The instantiated ZeroMQ context (i.e. zmq.Context())
            passed in from the application.
        barrier (object): Threading Barrier object used to sync threads, for
            the main thread to ensure socket setup has finished.

    Usage:
        * Define endpoints using the ``expose`` decorator.
        * Call endpoints using the function name.

    Message interface:
        * Accepts requests of the format: {"command": CMD, "args": {...}}
        * Returns responses of the format: {"data": {...}}
        * Returns error in the format: {"error": {"message": MSG}}

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

    RECV_TIMEOUT = 1
    """Max time the SuiteRuntimeServer will wait for an incoming
    message in seconds.

    We use a timeout here so as to give the _listener a chance to respond to
    requests (i.e. stop) from its spawner (the scheduler).

    The alternative would be to spin up a client and send a message to the
    server, this way seems safer.

    """

    def __init__(self, schd, context=None, barrier=None,
                 threaded=True, daemon=False):
        super().__init__(zmq.REP, bind=True, context=context,
                         barrier=barrier, threaded=threaded, daemon=daemon)
        self.schd = schd
        self.suite = schd.suite
        self.public_priv = None  # update in get_public_priv()
        self.endpoints = None
        self.queue = None
        self.resolvers = Resolvers(
            self.schd.data_store_mgr,
            schd=self.schd
        )
        self.middleware = [
            IgnoreFieldMiddleware,
        ]

    def _socket_options(self):
        """Set socket options.

        Overwrites Base method.

        """
        # create socket
        self.socket.RCVTIMEO = int(self.RECV_TIMEOUT) * 1000

    def _bespoke_start(self):
        """Setup start items, and run listener.

        Overwrites Base method.

        """
        # start accepting requests
        self.queue = Queue()
        self.register_endpoints()
        self._listener()

    def _bespoke_stop(self):
        """Stop the listener and Authenticator.

        Overwrites Base method.

        """
        LOG.debug('stopping zmq server...')
        self.stopping = True
        if self.queue is not None:
            self.queue.put('STOP')

    def _listener(self):
        """The server main loop, listen for and serve requests."""
        while True:
            # process any commands passed to the listener by its parent process
            if self.queue.qsize():
                command = self.queue.get()
                if command == 'STOP':
                    break
                raise ValueError('Unknown command "%s"' % command)

            try:
                # wait RECV_TIMEOUT for a message
                msg = self.socket.recv_string()
            except zmq.error.Again:
                # timeout, continue with the loop, this allows the listener
                # thread to stop
                continue
            except zmq.error.ZMQError as exc:
                LOG.exception('unexpected error: %s', exc)
                continue

            # attempt to decode the message, authenticating the user in the
            # process
            try:
                message = decode_(msg)
            except Exception as exc:  # purposefully catch generic exception
                # failed to decode message, possibly resulting from failed
                # authentication
                LOG.exception('failed to decode message: "%s"', exc)
            else:
                # success case - serve the request
                res = self._receiver(message)
                if message['command'] in PB_METHOD_MAP:
                    response = res['data']
                else:
                    response = encode_(res).encode()
                # send back the string to bytes response
                self.socket.send(response)

            # Note: we are using CurveZMQ to secure the messages (see
            # self.curve_auth, self.socket.curve_...key etc.). We have set up
            # public-key cryptography on the ZMQ messaging and sockets, so
            # there is no need to encrypt messages ourselves before sending.

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

    def register_endpoints(self):
        """Register all exposed methods."""
        self.endpoints = {name: obj
                          for name, obj in self.__class__.__dict__.items()
                          if hasattr(obj, 'exposed')}

    @authorise(Priv.IDENTITY)
    @expose
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
    @expose
    def broadcast(
            self,
            mode,
            cycle_points=None,
            tasks=None,
            settings=None
    ):
        """Put or clear broadcasts."""
        if mode == 'put_broadcast':
            return self.schd.task_events_mgr.broadcast_mgr.put_broadcast(
                cycle_points, tasks, settings)
        if mode == 'clear_broadcast':
            return self.schd.task_events_mgr.broadcast_mgr.clear_broadcast(
                cycle_points, tasks, settings)
        # TODO implement other broadcast interfaces (i.e. expire, display)
        raise ValueError('Unsupported broadcast mode')

    @authorise(Priv.READ)
    @expose
    def graphql(self, request_string=None, variables=None):
        """Return the GraphQL scheme execution result.

        Args:
            request_string (str, optional):
                GraphQL request passed to Graphene
            variables (dict, optional):
                Dict of variables passed to Graphene

        Returns:
            object: Execution result, or a list with errors.
        """
        try:
            executed = schema.execute(
                request_string,
                variable_values=variables,
                context={
                    'resolvers': self.resolvers,
                },
                backend=CylcGraphQLBackend(),
                middleware=list(instantiate_middleware(self.middleware)),
                executor=AsyncioExecutor(),
                validate=True,  # validate schema (dev only? default is True)
                return_promise=False,
            )
        except Exception as exc:
            return 'ERROR: GraphQL execution error \n%s' % exc
        if executed.errors:
            errors = []
            for error in executed.errors:
                if hasattr(error, '__traceback__'):
                    import traceback
                    errors.append({'error': {
                        'message': str(error),
                        'traceback': traceback.format_exception(
                            error.__class__, error, error.__traceback__)}})
                    continue
                errors.append(getattr(error, 'message', None))
            return errors
        return executed.data

    # TODO: deprecated by broadcast()
    @authorise(Priv.CONTROL)
    @expose
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
    @expose
    def expire_broadcast(self, cutoff=None):
        """Clear all settings targeting cycle points earlier than cutoff.

        Args:
            cutoff (str, optional):
                Cycle point, broadcasts earlier than but not inclusive of the
                cutoff will be canceled.

        """
        return self.schd.task_events_mgr.broadcast_mgr.expire_broadcast(cutoff)

    @authorise(Priv.READ)
    @expose
    def get_broadcast(self, task_id=None):
        """Retrieve all broadcast variables that target a given task ID.

        Args:
            task_id (str, optional): A `task identifier`_

        Returns:
            dict: all broadcast variables that target the given task ID.

        """
        return self.schd.task_events_mgr.broadcast_mgr.get_broadcast(task_id)

    @authorise(Priv.IDENTITY)
    @expose
    def get_cylc_version(self):
        """Return the cylc version running this suite."""
        return CYLC_VERSION

    @authorise(Priv.READ)
    @expose
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
    @expose
    def get_suite_info(self):
        """Return a dictionary containing the suite title and description.

        Returns:
            dict: The `[meta]` section of a suite configuration

        """
        return self.schd.info_get_suite_info()

    @authorise(Priv.READ)
    @expose
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
    @expose
    def get_task_info(self, names):
        """Return the configurations for the provided tasks.

        Args:
            names (list): A list of task names to request information for.

        Returns:
            dict: Dictionary in the format ``{'task': {...}, ...}``

        """
        return self.schd.info_get_task_info(names)

    @authorise(Priv.READ)
    @expose
    def get_task_jobfile_path(self, task_id):
        """Return task job file path.

        Args:
            task_id: A `task identifier`_

        Returns:
            str: The jobfile path.

        """
        return self.schd.info_get_task_jobfile_path(task_id)

    @authorise(Priv.READ)
    @expose
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
    @expose
    def hold(self, tasks=None, time=None):
        """Hold the workflow."""
        self.schd.command_queue.put((
            'hold',
            tuple(),
            filter_none({
                'tasks': tasks,
                'time': time
            })
        ))
        return (True, 'Command queued')

    # TODO: deprecated by hold()
    @authorise(Priv.CONTROL)
    @expose
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

    # TODO: deprecated by hold()
    @authorise(Priv.CONTROL)
    @expose
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

    # TODO: deprecated by hold()
    @authorise(Priv.CONTROL)
    @expose
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
    @expose
    def identify(self):
        """Return basic information about the suite.

        Returns:
            dict: Dictionary containing the keys

            cylc.flow.suite_status.KEY_NAME
               The suite name.
            cylc.flow.suite_status.KEY_OWNER
               The user account the suite is running under.
            cylc.flow.suite_status.KEY_VERSION
               The Cylc version the suite is running with.

        """
        return {
            KEY_NAME: self.schd.suite,
            KEY_OWNER: self.schd.owner,
            KEY_VERSION: CYLC_VERSION
        }

    @authorise(Priv.DESCRIPTION)
    @expose
    def describe(self):
        """Return the suite metadata.]

        Returns:
            dict: ``{cylc.flow.suite_status: { ... }}``

        """
        return {KEY_META: self.schd.config.cfg[KEY_META]}

    @authorise(Priv.STATE_TOTALS)
    @expose
    def state_totals(self):
        """Returns counts of the task states present in the suite.

        Returns:
            dict: Dictionary with the keys:

            cylc.flow.suite_status.KEY_UPDATE_TIME
               ISO8601 timestamp of when this data snapshot was made.
            cylc.flow.suite_status.KEY_STATES
               Tuple of the form ``(state_count_totals, state_count_cycles)``

               state_count_totals (dict):
                  Dictionary of the form ``{task_state: task_count}``.
               state_count_cycles (dict):
                  Dictionary of the form ``{cycle_point: task_count}``.
            cylc.flow.suite_status.KEY_TASKS_BY_STATE
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
    @expose
    def kill_tasks(self, tasks):
        """Kill task jobs.

        Args:
            tasks (list): List of identifiers, see `task globs`_

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("kill_tasks", (tasks,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @expose
    def remove_tasks(self, tasks):
        """Remove tasks from the task pool.

        Args:
            tasks (list):
                List of identifiers, see `task globs`

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("remove_tasks", (tasks,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @expose
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
    @expose
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
    @expose
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
    @expose
    def poll_tasks(self, tasks=None, poll_succeeded=False):
        """Request the suite to poll task jobs.

        Args:
            tasks (list, optional):
                List of identifiers, see `task globs`_
            poll_succeeded (bool, optional):
                Allow polling of remote tasks if True.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("poll_tasks", (tasks,), {"poll_succ": poll_succeeded}))
        return (True, 'Command queued')

    # TODO: deprecated by broadcast()
    @authorise(Priv.CONTROL)
    @expose
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
    @expose
    def put_ext_trigger(self, message, id):
        """Server-side external event trigger interface.

        Args:
            message (str): The external trigger message.
            id (str): The unique trigger ID.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.ext_trigger_queue.put((message, id))
        return (True, 'Event queued')

    @authorise(Priv.CONTROL)
    @expose
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
    @expose
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
    @expose
    def release(self, tasks=None):
        """Release (un-hold) the workflow."""
        if tasks:
            self.schd.command_queue.put(("release_tasks", (tasks,), {}))
        else:
            self.schd.command_queue.put(("release_suite", (), {}))
        return (True, 'Command queued')

    # TODO: deprecated by release()
    @authorise(Priv.CONTROL)
    @expose
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

    # TODO: deprecated by release()
    @authorise(Priv.CONTROL)
    @expose
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

    # TODO: deprecated by stop()
    @authorise(Priv.SHUTDOWN)
    @expose
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

    # TODO: deprecated by stop()
    @authorise(Priv.SHUTDOWN)
    @expose
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

    # TODO: deprecated by stop()
    @authorise(Priv.SHUTDOWN)
    @expose
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

    # TODO: deprecated by stop()
    @authorise(Priv.SHUTDOWN)
    @expose
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
    @expose
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
    @expose
    def force_spawn_children(self, tasks, outputs):
        """Spawn children of given task outputs.

        Args:
            tasks (list): List of identifiers, see `task globs`
            outputs (list): List of outputs to spawn on

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("force_spawn_children", (tasks,),
             {'outputs': outputs}))
        return (True, 'Command queued')

    @authorise(Priv.SHUTDOWN)
    @expose
    def stop_workflow(
            self,
            mode=None,
            cycle_point=None,
            clock_time=None,
            task=None
    ):
        """Stop the workflow."""

        self.schd.command_queue.put((
            "stop",
            (),
            filter_none({
                'mode': mode,
                'cycle_point': cycle_point,
                'clock_time': clock_time,
                'task': task
            })
        ))
        return (True, 'Command queued')

    # TODO: deprecated by stop()
    @authorise(Priv.SHUTDOWN)
    @expose
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
    @expose
    def stop_flow(self, flow_label):
        """Stop a specified flow from spawning any further.

        Args:
            flow_label (str): the flow to stop

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("stop_flow", (flow_label,), {}))
        return (True, 'Command queued')

    @authorise(Priv.CONTROL)
    @expose
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
    @expose
    def force_trigger_tasks(self, tasks, reflow=False):
        """Trigger submission of task jobs where possible.

        Args:
            tasks (list):
                List of identifiers, see `task globs`_
            reflow (bool, optional):
                Start new flow(s) from triggered tasks.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("force_trigger_tasks", (tasks,),
             {"reflow": reflow}))
        return (True, 'Command queued')

    # UIServer Data Commands
    @authorise(Priv.READ)
    @expose
    def pb_entire_workflow(self):
        """Send the entire data-store in a single Protobuf message.

        Returns:
            bytes
                Serialised Protobuf message

        """
        pb_msg = self.schd.data_store_mgr.get_entire_workflow()
        return pb_msg.SerializeToString()

    @authorise(Priv.READ)
    @expose
    def pb_data_elements(self, element_type):
        """Send the specified data elements in delta form.

        Args:
            element_type (str):
                Key from DELTAS_MAP dictionary.

        Returns:
            bytes
                Serialised Protobuf message

        """
        pb_msg = self.schd.data_store_mgr.get_data_elements(element_type)
        return pb_msg.SerializeToString()

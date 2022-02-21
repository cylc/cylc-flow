# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
"""Server for workflow runtime API."""

import getpass  # noqa: F401
from queue import Queue
from textwrap import dedent
from time import sleep
from typing import Any, Dict, List, Optional, Union

from graphql.execution import ExecutionResult
from graphql.execution.executors.asyncio import AsyncioExecutor
import zmq

from cylc.flow import LOG
from cylc.flow.network import encode_, decode_, ZMQSocketBase
from cylc.flow.network.authorisation import authorise
from cylc.flow.network.graphql import (
    CylcGraphQLBackend, IgnoreFieldMiddleware, instantiate_middleware
)
from cylc.flow.network.resolvers import Resolvers
from cylc.flow.network.schema import schema
from cylc.flow.data_store_mgr import DELTAS_MAP
from cylc.flow.data_messages_pb2 import PbEntireWorkflow  # type: ignore


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


class WorkflowRuntimeServer(ZMQSocketBase):
    """Workflow runtime service API facade exposed via zmq.

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

        task identifier (str):
            A task identifier in the format ``cycle-point/task-name``
            e.g. ``1/foo`` or ``20000101T0000Z/bar``.

        .. _task globs:

        task globs (list):
            A list of Cylc IDs relative to the workflow.

            * ``1`` - The cycle point "1".
            * ``1/foo`` - The task "foo" in the cycle "1".
            * ``1/foo/01`` - The first job of the task "foo" from the cycle
              "1".

            Glob-like patterns may be used to match multiple items e.g.

            ``*``
               Matches everything.
            ``1/*``
               Matches everything in cycle ``1``.
            ``*/*:failed``
               Matches all failed tasks.

    """

    RECV_TIMEOUT = 1
    """Max time the WorkflowRuntimeServer will wait for an incoming
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
        self.workflow = schd.workflow
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

    def _listener(self) -> None:
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

    def register_endpoints(self):
        """Register all exposed methods."""
        self.endpoints = {name: obj
                          for name, obj in self.__class__.__dict__.items()
                          if hasattr(obj, 'exposed')}

    @authorise()
    @expose
    def api(
        self,
        endpoint: Optional[str] = None,
        **_kwargs
    ) -> Union[str, List[str]]:
        """Return information about this API.

        Returns a list of callable endpoints.

        Args:
            endpoint:
                If specified the documentation for the endpoint
                will be returned instead.

        Returns:
            List of endpoints or string documentation of the
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

    @authorise()
    @expose
    def graphql(
        self,
        request_string: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None
    ):
        """Return the GraphQL schema execution result.

        Args:
            request_string: GraphQL request passed to Graphene.
            variables: Dict of variables passed to Graphene.
            meta: Dict containing auth user etc.

        Returns:
            object: Execution result, or a list with errors.
        """
        try:
            executed: ExecutionResult = schema.execute(
                request_string,
                variable_values=variables,
                context_value={
                    'resolvers': self.resolvers,
                    'meta': meta or {},
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
            errors: List[Any] = []
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

    # UIServer Data Commands
    @authorise()
    @expose
    def pb_entire_workflow(self, **_kwargs) -> bytes:
        """Send the entire data-store in a single Protobuf message.

        Returns serialised Protobuf message

        """
        pb_msg = self.schd.data_store_mgr.get_entire_workflow()
        return pb_msg.SerializeToString()

    @authorise()
    @expose
    def pb_data_elements(self, element_type: str, **_kwargs) -> bytes:
        """Send the specified data elements in delta form.

        Args:
            element_type: Key from DELTAS_MAP dictionary.

        Returns serialised Protobuf message

        """
        pb_msg = self.schd.data_store_mgr.get_data_elements(element_type)
        return pb_msg.SerializeToString()

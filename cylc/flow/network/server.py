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

import asyncio
from queue import Queue
from textwrap import dedent
from time import sleep
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Union

from graphql.execution.executors.asyncio import AsyncioExecutor
import zmq
from zmq.auth.thread import ThreadAuthenticator

from cylc.flow import LOG, workflow_files
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.network.authorisation import authorise
from cylc.flow.network.graphql import (
    CylcGraphQLBackend, IgnoreFieldMiddleware, instantiate_middleware
)
from cylc.flow.network.publisher import WorkflowPublisher
from cylc.flow.network.replier import WorkflowReplier
from cylc.flow.network.resolvers import Resolvers
from cylc.flow.network.schema import schema
from cylc.flow.data_store_mgr import DELTAS_MAP
from cylc.flow.data_messages_pb2 import PbEntireWorkflow  # type: ignore

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler
    from graphql.execution import ExecutionResult

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


class WorkflowRuntimeServer:
    """Workflow runtime service API facade exposed via zmq.

    This class starts and coordinates the publisher and replier, and
    contains the Cylc endpoints invoked by the receiver to provide a response
    to incoming messages.

    Args:
        schd (object): The parent object instantiating the server. In
            this case, the workflow scheduler.

    Usage:
        * Define endpoints using the ``expose`` decorator.
        * Endpoints are called via the receiver using the function name.

    Message interface:
        * Accepts messages of the format: {"command": CMD, "args": {...}}
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
    endpoints: Dict[str, object]

    OPERATE_SLEEP_INTERVAL = 0.2
    STOP_SLEEP_INTERVAL = 0.2

    def __init__(self, schd):

        self.zmq_context = None
        self.port = None
        self.pub_port = None
        self.replier = None
        self.publisher = None
        self.loop = None
        self.thread = None
        self.curve_auth = None
        self.client_pub_key_dir = None

        self.schd: 'Scheduler' = schd
        self.resolvers = Resolvers(
            self.schd.data_store_mgr,
            schd=self.schd
        )
        self.middleware = [
            IgnoreFieldMiddleware,
        ]

        self.publish_queue: 'Queue[Iterable[tuple]]' = Queue()
        self.waiting_to_stop = False
        self.stopped = True

        self.register_endpoints()

    def start(self, barrier):
        """Start the TCP servers."""
        # set asyncio loop on thread
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        # TODO: this in zmq asyncio context?
        # Requires the scheduler main loop in asyncio first
        # And use of concurrent.futures.ThreadPoolExecutor?
        self.zmq_context = zmq.Context()
        # create an authenticator for the ZMQ context
        self.curve_auth = ThreadAuthenticator(self.zmq_context, log=LOG)
        self.curve_auth.start()  # start the authentication thread

        # Setting the location means that the CurveZMQ auth will only
        # accept public client certificates from the given directory, as
        # generated by a user when they initiate a ZMQ socket ready to
        # connect to a server.
        workflow_srv_dir = workflow_files.get_workflow_srv_dir(
            self.schd.workflow)
        client_pub_keyinfo = workflow_files.KeyInfo(
            workflow_files.KeyType.PUBLIC,
            workflow_files.KeyOwner.CLIENT,
            workflow_srv_dir=workflow_srv_dir)
        self.client_pub_key_dir = client_pub_keyinfo.key_path

        # Initial load for the localhost key.
        self.curve_auth.configure_curve(
            domain='*',
            location=(self.client_pub_key_dir)
        )

        min_, max_ = glbl_cfg().get(['scheduler', 'run hosts', 'ports'])
        self.replier = WorkflowReplier(self, context=self.zmq_context)
        self.replier.start(min_, max_)
        self.publisher = WorkflowPublisher(
            self.schd.workflow, context=self.zmq_context
        )
        self.publisher.start(min_, max_)
        self.port = self.replier.port
        self.pub_port = self.publisher.port
        self.schd.data_store_mgr.delta_workflow_ports()

        # wait for threads to setup socket ports before continuing
        barrier.wait()

        self.stopped = False

        self.operate()

    async def stop(self, reason: Union[BaseException, str]) -> None:
        """Stop the TCP servers, and clean up authentication.

        This method must be called/awaited from a different thread to the
        server's self.thread in order to interrupt the self.operate() loop
        and wait for self.thread to terminate.
        """
        self.waiting_to_stop = True
        if self.thread and self.thread.is_alive():
            # Wait for self.operate() loop to finish:
            while self.waiting_to_stop:
                # Non-async sleep - yield to other threads rather than
                # event loop (allows self.operate() running in different
                # thread to return)
                sleep(self.STOP_SLEEP_INTERVAL)

        if self.replier:
            self.replier.stop(stop_loop=False)
        if self.publisher:
            await self.publish_queued_items()
            await self.publisher.publish(
                (b'shutdown', str(reason).encode('utf-8'))
            )
            self.publisher.stop(stop_loop=False)
            self.publisher = None
        if self.curve_auth:
            self.curve_auth.stop()  # stop the authentication thread
        if self.loop and self.loop.is_running():
            self.loop.stop()
        if self.thread and self.thread.is_alive():
            self.thread.join()  # Wait for processes to return

        self.stopped = True

    def operate(self) -> None:
        """Orchestrate the receive, send, publish of messages."""
        # Note: this cannot be an async method because the response part
        # of the listener runs the event loop synchronously
        # (in graphql AsyncioExecutor)
        while True:
            if self.waiting_to_stop:
                # The self.stop() method is waiting for us to signal that we
                # have finished here
                self.waiting_to_stop = False
                return

            # Gather and respond to any requests.
            self.replier.listener()
            # Publish all requested/queued.
            self.loop.run_until_complete(self.publish_queued_items())

            # Yield control to other threads
            sleep(self.OPERATE_SLEEP_INTERVAL)

    async def publish_queued_items(self) -> None:
        """Publish all queued items."""
        while self.publish_queue.qsize():
            articles = self.publish_queue.get()
            await self.publisher.publish(*articles)

    def receiver(self, message):
        """Process incoming messages and coordinate response.

        Wrap incoming messages, dispatch them to exposed methods and/or
        coordinate a publishing stream.

        Args:
            message (dict): message contents
        """
        # TODO: If requested, coordinate publishing response/stream.

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
            executed: 'ExecutionResult' = schema.execute(
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
                LOG.error(error)
                if hasattr(error, '__traceback__'):
                    import traceback
                    formatted_tb = traceback.format_exception(
                        type(error), error, error.__traceback__
                    )
                    LOG.error("".join(formatted_tb))
                    errors.append({
                        'error': {
                            'message': str(error),
                            'traceback': formatted_tb
                        }
                    })
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

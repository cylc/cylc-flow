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
"""Client for workflow runtime API."""

from abc import (
    ABCMeta,
    abstractmethod,
)
import asyncio
import getpass
import os
from shutil import which
import socket
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Optional,
    Union,
)

import zmq
import zmq.asyncio

from cylc.flow import (
    LOG,
    __version__ as CYLC_VERSION,
)
from cylc.flow.exceptions import (
    ClientTimeout,
    ContactFileExists,
    CylcError,
    RequestError,
    WorkflowStopped,
)
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.network import (
    ZMQSocketBase,
    deserialize,
    get_location,
    serialize,
)
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.network.server import PB_METHOD_MAP
from cylc.flow.workflow_files import detect_old_contact_file


if TYPE_CHECKING:
    from cylc.flow.network import ResponseDict


class WorkflowRuntimeClientBase(metaclass=ABCMeta):
    """Base class for WorkflowRuntimeClients.

    WorkflowRuntimeClients that inherit from this must implement an async
    method ``async_request()``. This base class provides a ``serial_request()``
    method based on the ``async_request()`` method, callable by ``__call__``.
    It also provides a comms timeout handler method.
    """

    DEFAULT_TIMEOUT = 5  # seconds

    def __init__(
        self,
        workflow: str,
        host: Optional[str] = None,
        port: Union[int, str, None] = None,
        timeout: Union[float, str, None] = None
    ):
        self.workflow = workflow
        if not host or not port:
            host, port, _ = get_location(workflow)
        else:
            port = int(port)
        self.host = self._orig_host = host
        self.port = self._orig_port = port
        self.timeout = (
            float(timeout) if timeout is not None else self.DEFAULT_TIMEOUT
        )

    @abstractmethod
    async def async_request(
        self,
        command: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        req_meta: Optional[Dict[str, Any]] = None
    ) -> object:
        """Send an asynchronous request."""
        ...

    def serial_request(
        self,
        command: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        req_meta: Optional[Dict[str, Any]] = None
    ) -> object:
        """Send a request.

        For convenience use ``__call__`` to call this method.

        Args:
            command: The name of the endpoint to call.
            args: Arguments to pass to the endpoint function.
            timeout: Override the default timeout (seconds).

        Raises:
            ClientTimeout: If a response takes longer than timeout to arrive.
            ClientError: Coverall for all other issues including failed auth.

        Returns:
            object: The data exactly as returned from the endpoint function,
                nothing more, nothing less.

        """
        loop = getattr(self, 'loop', asyncio.new_event_loop())
        task = loop.create_task(
            self.async_request(command, args, timeout, req_meta)
        )
        loop.run_until_complete(task)
        if not hasattr(self, 'loop'):
            # (If inheriting class does have an event loop, don't mess with it)
            loop.close()
        return task.result()

    __call__ = serial_request

    def timeout_handler(self) -> None:
        """Handle the eventuality of a communication timeout with the workflow.

        Raises:
            WorkflowStopped: if the workflow has already stopped.
            CyclError: if the workflow has moved to different host/port.
        """
        contact_host, contact_port, _ = get_location(self.workflow)
        if (
            contact_host != get_fqdn_by_host(self._orig_host)
            or contact_port != self._orig_port
        ):
            raise CylcError(
                'The workflow is no longer running at '
                f'{self._orig_host}:{self._orig_port}\n'
                f'It has moved to {contact_host}:{contact_port}'
            )

        if os.getenv('CYLC_TASK_COMMS_METHOD'):
            # don't attempt to clean up old contact files in task messages
            return

        # Cannot connect, perhaps workflow is no longer running and is leaving
        # behind a contact file?
        try:
            detect_old_contact_file(self.workflow)
        except ContactFileExists:
            # old contact file exists and the workflow process still alive
            return
        else:
            # the workflow has stopped
            raise WorkflowStopped(self.workflow)


class WorkflowRuntimeClient(  # type: ignore[misc]
    ZMQSocketBase, WorkflowRuntimeClientBase
):
    # (Ignoring mypy 'definition of "host" in base class "ZMQSocketBase" is
    # incompatible with definition in base class "WorkflowRuntimeClientBase"')
    """Initiate a client to the scheduler API.

    Initiates the REQ part of a ZMQ REQ-REP pair.

    This class contains the logic for the ZMQ message interface and client -
    server communication.

    Determine host and port from the contact file unless provided.

    If there is no socket bound to the specified host/port the client will
    bail after ``timeout`` seconds.

    Args:
        workflow:
            Name of the workflow to connect to.
        timeout:
            Set the default timeout in seconds. The default is
            ``ZMQClient.DEFAULT_TIMEOUT``.
            Note the default timeout can be overridden for individual requests.
        host:
            The host where the flow is running if known.

            If both host and port are provided it is not necessary to load
            the contact file.
        port:
            The port on which the REQ-REP TCP server is listening.

            If both host and port are provided it is not necessary to load
            the contact file.

    Attributes:
        host:
            Workflow host name.
        port:
            Workflow host port.
        timeout_handler:
            Optional function which runs before ClientTimeout is raised.
            This provides an interface for raising more specific exceptions in
            the event of a communication timeout.
        header:
            Request "header" data to attach to each request.

    Usage:
        Call endpoints using ``ZMQClient.__call__``.

    Message interface:
        * Accepts responses of the format: {"data": {...}}
        * Accepts error in the format: {"error": {"message": MSG}}
        * Returns requests of the format: {"command": CMD,
          "args": {...}}

    Raises:
        WorkflowStopped: if the workflow is not running.

    Call server "endpoints" using:
        ``__call__``, ``serial_request``
            .. automethod::
                cylc.flow.network.client.WorkflowRuntimeClient.serial_request

        ``async_request``
            .. automethod::
                cylc.flow.network.client.WorkflowRuntimeClient.async_request

    """
    # socket & event loop not None - get assigned on init by self.start():
    socket: zmq.asyncio.Socket
    loop: asyncio.AbstractEventLoop

    def __init__(
        self,
        workflow: str,
        host: Optional[str] = None,
        port: Union[int, str, None] = None,
        timeout: Union[float, str, None] = None,
        context: Optional[zmq.asyncio.Context] = None,
        srv_public_key_loc: Optional[str] = None
    ):
        ZMQSocketBase.__init__(self, zmq.REQ, workflow, context=context)
        WorkflowRuntimeClientBase.__init__(self, workflow, host, port, timeout)
        # convert to milliseconds:
        self.timeout *= 1000
        self.poller: Any = None
        # Connect the ZMQ socket on instantiation
        self.start(self.host, self.port, srv_public_key_loc)
        # gather header info post start
        self.header = self.get_header()

    def _socket_options(self):
        """Set socket options after socket instantiation before connect.

        Overwrites Base method.

        """
        # if there is no server don't keep the client hanging around
        self.socket.setsockopt(zmq.LINGER, int(self.DEFAULT_TIMEOUT))

        # create a poller to handle timeouts
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

    async def async_request(
        self,
        command: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        req_meta: Optional[Dict[str, Any]] = None
    ) -> object:
        """Send an asynchronous request using asyncio.

        Has the same arguments and return values as ``serial_request``.

        """
        timeout = (float(timeout) * 1000 if timeout else None) or self.timeout
        if not args:
            args = {}

        # Note: we are using CurveZMQ to secure the messages (see
        # self.curve_auth, self.socket.curve_...key etc.). We have set up
        # public-key cryptography on the ZMQ messaging and sockets, so
        # there is no need to encrypt messages ourselves before sending.

        # send message
        msg: Dict[str, Any] = {'command': command, 'args': args}
        msg.update(self.header)
        # add the request metadata
        if req_meta:
            msg['meta'].update(req_meta)
        LOG.debug('zmq:send %s', msg)
        message = serialize(msg)
        self.socket.send_string(message)

        # receive response
        if self.poller.poll(timeout):
            res: bytes = await self.socket.recv()
        else:
            self.timeout_handler()
            raise ClientTimeout(
                'Timeout waiting for server response.'
                ' This could be due to network or server issues.'
                '\n* You might want to increase the timeout using the'
                ' --comms-timeout option;'
                '\n* or check the workflow log.'
            )
        LOG.debug('zmq:recv %s', res)

        if command in PB_METHOD_MAP:
            return res

        response: ResponseDict = deserialize(res.decode())

        try:
            return response['data']
        except KeyError:
            error = response.get('error')
            if isinstance(error, dict):
                error = error.get('message', error)
            if not error:
                error = (
                    f"Received invalid response for Cylc {CYLC_VERSION}: "
                    f"{response}"
                )
            raise RequestError(
                str(error), response.get('cylc_version')
            ) from None

    def get_header(self) -> dict:
        """Return "header" data to attach to each request for traceability.

        Returns:
            dict: dictionary with the header information, such as
                program and hostname.
        """
        host = socket.gethostname()
        if len(sys.argv) > 1:
            cmd = sys.argv[1]
        else:
            cmd = sys.argv[0]

        cylc_executable_location = which("cylc")
        if cylc_executable_location:
            cylc_bin_dir = os.path.abspath(
                os.path.join(cylc_executable_location, os.pardir)
            )
            if not cylc_bin_dir.endswith("/"):
                cylc_bin_dir = f"{cylc_bin_dir}/"

            if cmd.startswith(cylc_bin_dir):
                cmd = cmd.replace(cylc_bin_dir, '')
        try:
            behalf_of = f" (possibly on behalf of {os.getlogin()})"
        except OSError:
            behalf_of = None
        if not behalf_of:
            try:
                behalf_of = f" (possibly on behalf of {getpass.getuser()})"
            except OSError:
                behalf_of = ''

        return {
            'meta': {
                'prog': cmd,
                'host': host,
                'comms_method':
                    os.getenv(
                        "CLIENT_COMMS_METH",
                        default=CommsMeth.ZMQ.value
                    ),
                'behalf_of': behalf_of
            }
        }

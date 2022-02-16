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

from functools import partial
import os
from shutil import which
import socket
import sys
from typing import Any, Optional, Union, Dict

import zmq
import zmq.asyncio

from cylc.flow import LOG
from cylc.flow.exceptions import (
    ClientError,
    ClientTimeout,
    CylcError,
    ServiceFileError,
    WorkflowStopped,
)
from cylc.flow.network import (
    encode_,
    decode_,
    get_location,
    ZMQSocketBase
)
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.network.server import PB_METHOD_MAP
from cylc.flow.workflow_files import (
    ContactFileFields,
    detect_old_contact_file,
    load_contact_file
)


class WorkflowRuntimeClient(ZMQSocketBase):
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
        host (str):
            Workflow host name.
        port (int):
            Workflow host port.
        timeout_handler (function):
            Optional function which runs before ClientTimeout is raised.
            This provides an interface for raising more specific exceptions in
            the event of a communication timeout.
        header (dict):
            Request "header" data to attach to each request.

    Usage:
        Call endpoints using ``ZMQClient.__call__``.

    Message interface:
        * Accepts responses of the format: {"data": {...}}
        * Accepts error in the format: {"error": {"message": MSG}}
        * Returns requests of the format: {"command": CMD,
          "args": {...}}

    Raises:
        ClientError: if the workflow is not running.

    Call server "endpoints" using:
        ``__call__``, ``serial_request``
            .. automethod::
                cylc.flow.network.client.WorkflowRuntimeClient.serial_request

        ``async_request``
            .. automethod::
                cylc.flow.network.client.WorkflowRuntimeClient.async_request

    """

    DEFAULT_TIMEOUT = 5.  # 5 seconds

    def __init__(
        self,
        workflow: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        context=None,
        timeout: Union[float, str, None] = None,
        srv_public_key_loc: Optional[str] = None
    ):
        super().__init__(zmq.REQ, context=context)
        self.workflow = workflow
        if not host or not port:
            host, port, _ = get_location(workflow)
        else:
            port = int(port)
        self.host = host
        self.port = port
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        else:
            timeout = float(timeout)
        self.timeout = timeout * 1000
        self.timeout_handler = partial(
            self._timeout_handler, workflow, host, port)
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
        message = encode_(msg)
        self.socket.send_string(message)

        # receive response
        if self.poller.poll(timeout):
            res = await self.socket.recv()
        else:
            if callable(self.timeout_handler):
                self.timeout_handler()
            raise ClientTimeout(
                'Timeout waiting for server response.'
                ' This could be due to network or server issues.'
                ' Check the workflow log.'
            )

        if msg['command'] in PB_METHOD_MAP:
            response = {'data': res}
        else:
            response = decode_(res.decode())
        LOG.debug('zmq:recv %s', response)

        try:
            return response['data']
        except KeyError:
            error = response.get(
                'error',
                {'message': f'Received invalid response: {response}'},
            )
            raise ClientError(
                error.get('message'),
                error.get('traceback'),
            )

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
        task = self.loop.create_task(
            self.async_request(command, args, timeout, req_meta))
        self.loop.run_until_complete(task)
        return task.result()

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
        return {
            'meta': {
                'prog': cmd,
                'host': host,
                'comms_method':
                    os.getenv(
                        "CLIENT_COMMS_METH",
                        default=CommsMeth.ZMQ.value
                    )
            }
        }

    @staticmethod
    def _timeout_handler(workflow: str, host: str, port: Union[int, str]):
        """Handle the eventuality of a communication timeout with the workflow.

        Args:
            workflow (str): workflow name
            host (str): host name
            port (Union[int, str]): port number
        Raises:
            ClientError: if the workflow has already stopped.
        """
        if workflow is None:
            return

        try:
            contact_data: Dict[str, str] = load_contact_file(workflow)
        except (IOError, ValueError, ServiceFileError):
            # Contact file does not exist or corrupted, workflow should be dead
            return

        contact_host: str = contact_data.get(ContactFileFields.HOST, '?')
        contact_port: str = contact_data.get(ContactFileFields.PORT, '?')
        if (
            contact_host != host
            or contact_port != str(port)
        ):
            raise CylcError(
                f'The workflow is no longer running at {host}:{port}\n'
                f'It has moved to {contact_host}:{contact_port}'
            )

        # Cannot connect, perhaps workflow is no longer running and is leaving
        # behind a contact file?
        try:
            detect_old_contact_file(workflow, contact_data)
        except (AssertionError, ServiceFileError):
            # old contact file exists and the workflow process still alive
            return
        else:
            # the workflow has stopped
            raise WorkflowStopped(workflow)

    __call__ = serial_request

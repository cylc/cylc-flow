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
"""Client for suite runtime API."""

from functools import partial
import os
from shutil import which
import socket
import sys
from typing import Union

import zmq
import zmq.asyncio

from cylc.flow import LOG
from cylc.flow.exceptions import (
    ClientError,
    ClientTimeout,
    SuiteServiceFileError,
    SuiteStopped
)
from cylc.flow.network import (
    encode_,
    decode_,
    get_location,
    ZMQSocketBase
)
from cylc.flow.network.server import PB_METHOD_MAP
from cylc.flow.suite_files import detect_old_contact_file


class SuiteRuntimeClient(ZMQSocketBase):
    """Initiate a client to the workflow server API.

    Initiates the REQ part of a ZMQ REQ-REP pair.

    This class contains the logic for the ZMQ message interface and client -
    server communication.

    Determine host and port from the contact file unless provided.

    If there is no socket bound to the specified host/port the client will
    bail after ``timeout`` seconds.

    Args:
        suite (str):
            Name of the suite to connect to.
        owner (str):
            Owner of suite, defaults to $USER.
        host (str):
            Overt need to check contact file if provided along with the
            port.
        port (int):
            The port on the aforementioned host to connect to.
        timeout (float):
            Set the default timeout in seconds. The default is
            ``ZMQClient.DEFAULT_TIMEOUT``.
            Note the default timeout can be overridden for individual requests.
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
        ClientError: if the suite is not running.

    Call server "endpoints" using:
        ``__call__``, ``serial_request``
            .. automethod::
                cylc.flow.network.client.SuiteRuntimeClient.serial_request

        ``async_request``
            .. automethod::
                cylc.flow.network.client.SuiteRuntimeClient.async_request

    """

    DEFAULT_TIMEOUT = 5.  # 5 seconds

    def __init__(
            self,
            suite: str,
            owner: str = None,
            host: str = None,
            port: Union[int, str] = None,
            context: object = None,
            timeout: Union[float, str] = None,
            srv_public_key_loc: str = None
    ):
        super().__init__(zmq.REQ, context=context)
        self.suite = suite
        if port:
            port = int(port)
        if not (host and port):
            host, port, _ = get_location(suite, owner, host)
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        else:
            timeout = float(timeout)
        self.timeout = timeout * 1000
        self.timeout_handler = partial(
            self._timeout_handler, suite, host, port)
        self.poller = None
        # Connect the ZMQ socket on instantiation
        self.start(host, port, srv_public_key_loc)
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

    async def async_request(self, command, args=None, timeout=None):
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
        msg = {'command': command, 'args': args}
        msg.update(self.header)
        LOG.debug('zmq:send %s', msg)
        message = encode_(msg)
        self.socket.send_string(message)

        # receive response
        if self.poller.poll(timeout):
            res = await self.socket.recv()
        else:
            if callable(self.timeout_handler):
                self.timeout_handler()
            raise ClientTimeout('Timeout waiting for server response.')

        if msg['command'] in PB_METHOD_MAP:
            response = {'data': res}
        else:
            response = decode_(res.decode())
        LOG.debug('zmq:recv %s', response)

        try:
            return response['data']
        except KeyError:
            error = response['error']
            raise ClientError(error['message'], error.get('traceback'))

    def serial_request(self, command, args=None, timeout=None):
        """Send a request.

        For convenience use ``__call__`` to call this method.

        Args:
            command (str): The name of the endpoint to call.
            args (dict): Arguments to pass to the endpoint function.
            timeout (float): Override the default timeout (seconds).

        Raises:
            ClientTimeout: If a response takes longer than timeout to arrive.
            ClientError: Coverall for all other issues including failed auth.

        Returns:
            object: The data exactly as returned from the endpoint function,
                nothing more, nothing less.

        """
        task = self.loop.create_task(
            self.async_request(command, args, timeout))
        self.loop.run_until_complete(task)
        return task.result()

    @staticmethod
    def get_header() -> dict:
        """Return "header" data to attach to each request for traceability.

        Returns:
            dict: dictionary with the header information, such as
                program and hostname.
        """
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
                'host': socket.gethostname()
            }
        }

    @staticmethod
    def _timeout_handler(suite: str, host: str, port: Union[int, str]):
        """Handle the eventuality of a communication timeout with the suite.

        Args:
            suite (str): suite name
            host (str): host name
            port (Union[int, str]): port number
        Raises:
            ClientError: if the suite has already stopped.
        """
        if suite is None:
            return
        # Cannot connect, perhaps suite is no longer running and is leaving
        # behind a contact file?
        try:
            detect_old_contact_file(suite, (host, port))
        except (AssertionError, SuiteServiceFileError):
            # * contact file not have matching (host, port) to suite proc
            # * old contact file exists and the suite process still alive
            return
        else:
            # the suite has stopped
            raise SuiteStopped(suite)

    __call__ = serial_request

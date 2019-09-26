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
"""Client for suite runtime API."""

import asyncio
from functools import partial
import os
import socket
import sys
from typing import Union

import zmq
import zmq.asyncio

from shutil import which

from cylc.flow import LOG
from cylc.flow.exceptions import (
    ClientError,
    ClientTimeout,
    SuiteServiceFileError
)
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.network.authentication import (
    encode_, decode_, get_client_private_key_location)
from cylc.flow.network.server import PB_METHOD_MAP
from cylc.flow.suite_files import (
    ContactFileFields,
    UserFiles,
    detect_old_contact_file,
    load_contact_file
)

# we should only have one ZMQ context per-process
CONTEXT = zmq.asyncio.Context()


class ZMQClient(object):
    """Initiate the REQ part of a ZMQ REQ-REP pair.

    This class contains the logic for the ZMQ message interface and client -
    server communication.

    Args:
        host (str):
            The host to connect to.
        port (int):
            The port on the aforementioned host to connect to.
        encode_method (function):
            Translates outgoing messages into strings to be sent over the
            network. ``encode_method(json) -> str``
        decode_method (function):
            Translates incoming message strings into digestible data.
            ``decode_method(str) -> json``
        secret_key_loc (function):
            Return path of suite's secret keyfile for server communication.
        timeout (float):
            Set the default timeout in seconds. The default is
            ``ZMQClient.DEFAULT_TIMEOUT``.
            Note the default timeout can be overridden for individual requests.
        timeout_handler (function):
            Optional function which runs before ClientTimeout is raised.
            This provides an interface for raising more specific exceptions in
            the event of a communication timeout.
        header (dict): Request "header" data to attach to each request.

    Usage:
        * Call endpoints using ``ZMQClient.__call__``.

    Message interface:
        * Accepts responses of the format: {"data": {...}}
        * Accepts error in the format: {"error": {"message": MSG}}
        * Returns requests of the format: {"command": CMD,
        "args": {...}}

    """

    DEFAULT_TIMEOUT = 5.  # 5 seconds

    def __init__(
            self, host, port, encode_method, decode_method, secret_key_loc,
            timeout=None, timeout_handler=None, header=None):
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        else:
            timeout = float(timeout)
        self.timeout = timeout * 1000
        self.timeout_handler = timeout_handler

        self.secret_key = secret_key_loc
        try:
            secret = self.secret_key()
        # there is no need to encrypt messages ourselves before sending.
        except SuiteServiceFileError:
            raise ClientError("Could not read suite's private key file.")

        # open the ZMQ socket
        self.socket = CONTEXT.socket(zmq.REQ)

        # Fetch client keys, generated at registration, for authentication
        error_msg = "Failed to find suite's public key, so cannot connect."
        try:
            client_public_key, client_private_key = zmq.auth.load_certificate(
                secret)
        except (OSError, ValueError):
            raise ClientError(error_msg)
        if client_private_key is None:  # this cannot be caught by exception
            raise ClientError(error_msg)
        self.socket.curve_publickey = client_public_key
        self.socket.curve_secretkey = client_private_key

        # A client can only connect to the server if it knows its public key,
        # so we grab this from the location it was created on the filesystem:
        server_public_keyfile = os.path.join(
            UserFiles.get_user_certificate_full_path(),
            UserFiles.Auth.SERVER_PUBLIC_KEY_CERTIFICATE)
        try:
            # 'load_certificate' will try to load both public & private keys
            # from a provided file but will return None, not throw an error,
            # for the latter item if not there (as for all public key files) so
            # it is OK to use; there is no method to load only the public key.
            server_public_key = zmq.auth.load_certificate(
                server_public_keyfile)[0]  # ValueError raised w/ no public key
            self.socket.curve_serverkey = server_public_key
        except (OSError, ValueError):
            raise ClientError(
                "Failed to load server public key, so cannot connect.")

        self.socket.connect('tcp://%s:%d' % (host, port))
        # if there is no server don't keep the client hanging around
        self.socket.setsockopt(zmq.LINGER, int(self.DEFAULT_TIMEOUT))

        # create a poller to handle timeouts
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

        if not header:
            self.header = {}
        else:
            self.header = dict(header)

    async def async_request(self, command, args=None, timeout=None):
        """Send an asynchronous request using asyncio.

        Has the same arguments and return values as ``serial_request``.

        """
        if timeout:
            timeout = float(timeout)
        timeout = (timeout * 1000 if timeout else None) or self.timeout
        if not args:
            args = {}

        # Note: we are using CurveZMQ to secure the messages (see
        # self.curve_auth, self.socket.curve_...key etc.). We have set up
        # public-key cryptography on the ZMQ messaging and sockets, so
        # there is no need to encrypt messages ourselves before sending.

        # send message
        msg = {'command': command, 'args': args}
        msg.update(self.header)
        LOG.debug('zmq:send %s' % msg)
        message = encode_(msg)
        self.socket.send_string(message)

        # receive response
        if self.poller.poll(timeout):
            res = await self.socket.recv()
        else:
            if self.timeout_handler:
                self.timeout_handler()
            raise ClientTimeout('Timeout waiting for server response.')

        if msg['command'] in PB_METHOD_MAP:
            response = {'data': res}
        else:
            response = decode_(res.decode())
        LOG.debug('zmq:recv %s' % response)

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
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.async_request(command, args, timeout))
        loop.run_until_complete(task)
        return task.result()

    __call__ = serial_request


class SuiteRuntimeClient(ZMQClient):
    """This class contains the logic specific to communicating with Cylc
    suites.

    Call server "endpoints" using:

        ``__call__``, ``serial_request``

           .. automethod:: cylc.flow.network.client.ZMQClient.serial_request

        ``async_request``

           .. automethod:: cylc.flow.network.client.ZMQClient.async_request
    """

    def __init__(
            self,
            suite: str,
            owner: str = None,
            host: str = None,
            port: Union[int, str] = None,
            timeout: Union[float, str] = None
    ):
        """Initiate a client to the suite runtime API.

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
                Overt need to check contact file if provided along with the
                host.
            timeout (int):
                Message receive timeout in seconds. Also used to set the
                "linger" time, see ``ZMQClient``.
        Raises:
            ClientError: if the suite is not running.
        """
        if isinstance(timeout, str):
            timeout = float(timeout)
        if port:
            port = int(port)
        if not (host and port):
            host, port = self.get_location(suite, owner, host)

        super().__init__(
            host=host,
            port=port,
            encode_method=encode_,
            decode_method=decode_,
            secret_key_loc=partial(get_client_private_key_location, suite),
            timeout=timeout,
            header=self.get_header(),
            timeout_handler=partial(self._timeout_handler, suite, host, port)
        )

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
            raise ClientError('Suite "%s" already stopped' % suite)

    @classmethod
    def get_location(cls, suite: str, owner: str, host: str):
        """Extract host and port from a suite's contact file.

        NB: if it fails to load the suite contact file, it will exit.

        Args:
            suite (str): suite name
            owner (str): owner of the suite
            host (str): host name
        Returns:
            Tuple[str, int]: tuple with the host name and port number.
        Raises:
            ClientError: if the suite is not running.
        """
        try:
            contact = load_contact_file(
                suite, owner, host)
        except SuiteServiceFileError:
            raise ClientError(f'Contact info not found for suite '
                              f'"{suite}", suite not running?')

        if not host:
            host = contact[ContactFileFields.HOST]
        host = get_fqdn_by_host(host)

        port = int(contact[ContactFileFields.PORT])
        return host, port

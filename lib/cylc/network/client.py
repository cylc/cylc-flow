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
"""Client for suite runtime API."""

import asyncio
import os
import socket
import sys

import jose.exceptions
import zmq
import zmq.asyncio

from cylc import LOG
from cylc.exceptions import ClientError, ClientTimeout
import cylc.flags
from cylc.hostuserutil import get_fqdn_by_host
from cylc.network import encrypt, decrypt, get_secret
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)


# we should only have one ZMQ context per-process
CONTEXT = zmq.asyncio.Context()


class ZMQClient(object):
    """Initiate the REQ part of a ZMQ REQ-REP pair.

    This class contains the logic for the ZMQ message interface and client -
    server communication.

    NOTE: Security to be provided via the encode / decode interface.

    Args:
        host (str):
            The host to connect to.
        port (int):
            The port on the aforementioned host to connect to.
        encode_method (function):
            Translates outgoing messages into strings to be sent over the
            network. ``encode_method(json, secret) -> str``
        decode_method (function):
            Translates incoming message strings into digestible data.
            ``encode_method(str, secret) -> dict``
        secret_method (function):
            Return the secret for use with the encode/decode methods.
            Called for each encode / decode.
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
        * Returns requests of the format: {"command": CMD, "args": {...}}

    """

    DEFAULT_TIMEOUT = 5.  # 5 seconds

    def __init__(self, host, port, encode_method, decode_method, secret_method,
                 timeout=None, timeout_handler=None, header=None):
        self.encode = encode_method
        self.decode = decode_method
        self.secret = secret_method
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        else:
            timeout = float(timeout)
        self.timeout = timeout * 1000
        self.timeout_handler = timeout_handler

        # open the ZMQ socket
        self.socket = CONTEXT.socket(zmq.REQ)
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

        # get secret for this request
        # assumes secret won't change during the request
        try:
            secret = self.secret()
        except cylc.suite_srv_files_mgr.SuiteServiceFileError:
            raise ClientError('could not read suite passphrase')

        # send message
        msg = {'command': command, 'args': args}
        msg.update(self.header)
        LOG.debug('zmq:send %s' % msg)
        message = encrypt(msg, secret)
        self.socket.send_string(message)

        # receive response
        if self.poller.poll(timeout):
            res = await self.socket.recv_string()
        else:
            if self.timeout_handler:
                self.timeout_handler()
            raise ClientTimeout('Timeout waiting for server response.')

        try:
            response = decrypt(res, secret)
            LOG.debug('zmq:recv %s' % response)
        except jose.exceptions.JWTError:
            raise ClientError(
                'Could not decrypt response. Has the passphrase changed?')

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
        return asyncio.run(
            self.async_request(command, args, timeout))

    __call__ = serial_request


class SuiteRuntimeClient:
    """Initiate a client to the suite runtime API.

    This class contains the logic specific to communicating with Cylc suites.

    Args:
        suite (str):
            Name of the suite to connect to.
        owner (str):
            Owner of suite, defaults to $USER.
        host (str):
            Overt need to check contact file if provided along with the port.
        port (int):
            Overt need to check contact file if provided along with the host.
        timeout (int):
            Message receive timeout in seconds. Also used to set the
            "linger" time, see ``ZMQClient``.

    Determine host and port from the contact file unless provided.

    If there is no socket bound to the specified host/port the client will
    bail after ``timeout`` seconds.

    Call server "endpoints" using:

    ``__call__``, ``serial_request``

       .. automethod:: cylc.network.client.ZMQClient.serial_request

    ``async_request``

       .. automethod:: cylc.network.client.ZMQClient.async_request

    """

    NOT_RUNNING = "Contact info not found for suite \"%s\", suite not running?"

    def __new__(cls, suite, owner=None, host=None, port=None, timeout=None):
        if isinstance(timeout, str):
            timeout = float(timeout)

        # work out what we are connecting to
        if port:
            port = int(port)
        if not (host and port):
            host, port = cls.get_location(suite, owner, host)

        # create connection
        return ZMQClient(
            host, port, encrypt, decrypt, lambda: get_secret(suite),
            timeout=timeout, header=cls.get_header(),
            timeout_handler=lambda: cls._timeout_handler(suite, host, port)
        )

    @staticmethod
    def get_header():
        """Return "header" data to attach to each request for traceability."""
        CYLC_EXE = os.path.join(os.environ['CYLC_DIR'], 'bin', '')
        cmd = sys.argv[0]

        if cmd.startswith(CYLC_EXE):
            cmd = cmd.replace(CYLC_EXE, '')

        return {
            'meta': {
                'prog': cmd,
                'host': socket.gethostname()
            }
        }

    @staticmethod
    def _timeout_handler(suite, host, port):
        """Handle the eventuality of a communication timeout with the suite."""
        if suite is None:
            return
        # Cannot connect, perhaps suite is no longer running and is leaving
        # behind a contact file?
        try:
            SuiteSrvFilesManager().detect_old_contact_file(suite, (host, port))
        except (AssertionError, SuiteServiceFileError):
            # * contact file not have matching (host, port) to suite proc
            # * old contact file exists and the suite process still alive
            return
        else:
            # the suite has stopped
            raise ClientError('Suite "%s" already stopped' % suite)

    @classmethod
    def get_location(cls, suite, owner, host):
        """Extract host and port from a suite's contact file."""
        try:
            contact = SuiteSrvFilesManager().load_contact_file(
                suite, owner, host)
        except SuiteServiceFileError:
            sys.exit(cls.NOT_RUNNING % suite)
            # monkey-patch the error message to make it more informative.
            # exc.args = (cls.NOT_RUNNING % suite,)
            # raise

        if not host:
            host = contact[SuiteSrvFilesManager.KEY_HOST]
        host = get_fqdn_by_host(host)

        port = int(contact[SuiteSrvFilesManager.KEY_PORT])
        return host, port

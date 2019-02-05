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
"""HTTP(S) client for suite runtime API.

Implementation currently via requests (urllib3) or urllib2.
"""

import sys

import jose.exceptions
import zmq

import cylc.flags
from cylc.hostuserutil import get_host, get_fqdn_by_host
from cylc.network import encrypt, decrypt, get_secret
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)


class ClientError(Exception):
    # TODO: this is a bit messy, lets tidy
    # TODO: ServerError class

    def __init__(self, error):
        self.message = error.get('message',
            'Request failed but returned no error message.')
        traceback = error.get('traceback')
        self.traceback = '\n%s' % traceback if traceback else ''

    def __str__(self):
        ret = 'Request returned error: %s' % self.message
        if cylc.flags.debug:
            ret += self.traceback
        return ret


class ClientTimeout(Exception):
    pass


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

    Usage:
        * Call endpoints using ``ZMQClient.__call__``.

    Message interface:
        * Accepts responses of the format: {"data": {...}}
        * Accepts error in the format: {"error": {"message": MSG}}
        * Returns requests of the format: {"command": CMD, "args": {...}}

    """

    DEFAULT_TIMEOUT = 1.  # 1 second
    DEFAULT_TIMEOUT = 5.  # 5 second

    def __init__(self, host, port, encode_method, decode_method, secret_method,
                 timeout=None, timeout_handler=None):
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
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect('tcp://%s:%d' % (host, port))
        # if there is no server don't keep the client hanging around
        self.socket.setsockopt(zmq.LINGER, int(self.DEFAULT_TIMEOUT))

        # create a poller to handle timeouts
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

    def request(self, command, args=None, timeout=None):
        """Send a request.

        For convenience use __call__ to call this method.

        Args:
            command (str): The name of the endpoint to call.
            args (dict): Arguments to pass to the endpoint function.
            timeout (float): Override the default timeout (seconds).

        Raises:
            ClientTimeout: If a response takes longer than timeout to arrive.
            ClientError: Coverall for all other issues including failed
                authentication.

        Returns:
            object: The data exactly as returned from the endpoint function,
                nothing more, nothing less.

        """
        if timeout:
            timeout = float(timeout)
        timeout = (timeout * 1000 if timeout else None) or self.timeout
        if not args:
            args = {}

        # send message
        message = encrypt({"command": command, "args": args}, self.secret())
        self.socket.send_string(message)

        if self.poller.poll(timeout):
            res = self.socket.recv_string()
        else:
            if self.timeout_handler:
                self.timeout_handler()
            raise ClientTimeout('Timeout waiting for server response.')

        try:
            response = decrypt(res, self.secret())
        except jose.exceptions.JWTError:
            raise ClientError({
                'message': 'Could not decrypt response. Has the passphrase '
                           + 'changed?'})

        # return data or handle error
        if 'data' in response:
            return response['data']
        else:  # if else to avoid complicating the traceback stack
            raise ClientError(response['error'])

    __call__ = request


class SuiteRuntimeClient(ZMQClient):
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

    Determine host and port from the contact file unless they are both
    provided.

    If there is no socket bound to the specified host/port the client will
    bail after ``timeout`` seconds.

    TODO: Implement or remove:
    * my_uuid
    * print_uuid
    * auth

    """

    NOT_RUNNING = "Contact info not found for suite \"%s\", suite not running?"

    def __init__(self, suite, owner=None, host=None, port=None,
                 timeout=None, my_uuid=None, print_uuid=False, auth=None):
        self.suite = suite
        if isinstance(timeout, str):
            timeout = float(timeout)

        # work out what we are connecting to
        if host and port:
            port = int(port)
        elif host or port:
            raise ValueError('Provide both host and port')
        else:
            host, port = self.get_location(suite, owner, host)

        # create connection
        ZMQClient.__init__(
            self, host, port, encrypt, decrypt, lambda: get_secret(suite),
            timeout=timeout,
            timeout_handler=lambda: self._timeout_handler(suite, host, port)
        )

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
            raise ClientError(  # TODO: SuiteStoppedError?
                {'message': 'Suite "%s" already stopped' % suite})

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

        if host and host.split('.')[0] == 'localhost':
            host = get_host()
        elif host and '.' not in host:  # Not IP and no domain
            host = get_fqdn_by_host(host)
        else:
            host = contact[SuiteSrvFilesManager.KEY_HOST]
        port = int(contact[SuiteSrvFilesManager.KEY_PORT])
        return host, port

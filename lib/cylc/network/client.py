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

import zmq

from cylc.hostuserutil import get_host, get_fqdn_by_host
from cylc.network import encrypt, decrypt, get_secret
from cylc.suite_srv_files_mgr import SuiteSrvFilesManager


class ClientError(Exception):
    pass


class ClientTimeout(Exception):
    pass


class ZMQClient(object):

    def __init__(self, host, port, encode_method, decode_method, secret_method,
                 timeout=None):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect('tcp://%s:%d' % (host, port))
        self.encode = encode_method
        self.decode = decode_method
        self.secret = secret_method
        if timeout:
            # TODO: tidy / refine timeout setting somehow!
            self.set_timeout(timeout)

    def set_timeout(self, timeout):
        self.socket.RCVTIMEO = int(timeout)

    def request(self, command, args=None, timeout=None):
        if not args:
            args = {}
        if timeout is not None:
            old_timeout = timeout
            self.set_timeout(timeout)

        # send message
        message = encrypt({"command": command, "args": args}, self.secret())
        self.socket.send_string(message)

        # recieve message
        try:
            res = self.socket.recv_string()
        except zmq.error.Again:
            raise ClientTimeout('Timeout waiting for server response.')
        response = decrypt(res, self.secret())

        if timeout is not None:
            self.set_timeout(old_timeout)  # reset timeout

        # return data or handle error
        try:
            return response['data']
        except KeyError:
            try:
                raise ClientError('Server returned error message: %s' % (
                    response['error']['message']))
            except KeyError:
                raise ClientError('Server returned no data and no error '
                                  'message.\n%s' % response)

    __call__ = request


class SuiteRuntimeClient(ZMQClient):

    def __init__(self, suite, owner=None, host=None, port=None, timeout=None,
            my_uuid=None, print_uuid=False, auth=None):

        # TODO: Implement or remove:
        # * port
        # * my_uuid
        # * print_uuid
        # * auth

        #if not owner:
        #    owner = get_user()

        contact = SuiteSrvFilesManager().load_contact_file(suite)

        if host and host.split('.')[0] == 'localhost':
            host = get_host()
        elif host and '.' not in host:  # Not IP and no domain
            host = get_fqdn_by_host(host)
        else:
            host = contact[SuiteSrvFilesManager.KEY_HOST]

        if port:
            port = int(port)
        else:
            port = int(contact[SuiteSrvFilesManager.KEY_PORT])

        ZMQClient.__init__(self, host, port, encrypt, decrypt,
                           lambda: get_secret(suite), timeout=timeout)

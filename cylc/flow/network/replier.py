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
from time import sleep

import zmq

from cylc.flow import LOG
from cylc.flow.network import encode_, decode_, ZMQSocketBase


class WorkflowReplier(ZMQSocketBase):
    """Initiate the REP part of a ZMQ REQ-REP pattern.

    This class contains the logic for the ZMQ message replier.

    Usage:
        * Define ...

    """

    RECV_TIMEOUT = 1
    """Max time the Workflow Replier will wait for an incoming
    message in seconds.

    We use a timeout here so as to give the _listener a chance to respond to
    requests (i.e. stop) from its spawner (the scheduler).

    The alternative would be to spin up a client and send a message to the
    server, this way seems safer.

    """

    def __init__(self, server, context=None, barrier=None,
                 threaded=True, daemon=False):
        super().__init__(zmq.REP, bind=True, context=context,
                         barrier=barrier, threaded=threaded, daemon=daemon)
        self.server = server
        self.workflow = server.schd.workflow
        self.queue = None

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
                res = self.server.responder(message)
                # send back the string to bytes response
                if isinstance(res.get('data'), bytes):
                    response = res['data']
                else:
                    response = encode_(res).encode()
                self.socket.send(response)

            # Note: we are using CurveZMQ to secure the messages (see
            # self.curve_auth, self.socket.curve_...key etc.). We have set up
            # public-key cryptography on the ZMQ messaging and sockets, so
            # there is no need to encrypt messages ourselves before sending.

            sleep(0)  # yield control to other threads

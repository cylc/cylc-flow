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

from queue import Queue
from typing import TYPE_CHECKING, Optional

import zmq

from cylc.flow import LOG
from cylc.flow.network import encode_, decode_, ZMQSocketBase

if TYPE_CHECKING:
    from cylc.flow.network.server import WorkflowRuntimeServer


class WorkflowReplier(ZMQSocketBase):
    """Initiate the REP part of a ZMQ REQ-REP pattern.

    This class contains the logic for the ZMQ message replier. The REQ/REP
    pattern is serial, in that it cannot REQ or REP twice in a row. After
    receiving you must send a response.

    Usage:
        * Start the replier.
        * Call the listener to process incoming REQ and send the REP.

    Message Processing:
        * Calls the server's receiver to process the command and
            obtain a response.

    Message interface:
        * Expects requests of the format: {"command": CMD, "args": {...}}
        * Sends responses of the format: {"data": {...}}
        * Sends errors in the format: {"error": {"message": MSG}}

    """

    def __init__(
        self,
        server: 'WorkflowRuntimeServer',
        context: Optional[zmq.Context] = None
    ):
        super().__init__(
            zmq.REP, server.schd.workflow, bind=True, context=context
        )
        self.server = server
        self.queue: 'Queue[str]' = Queue()

    def _bespoke_stop(self) -> None:
        """Stop the listener and Authenticator.

        Overwrites Base method.

        """
        LOG.debug('stopping zmq replier...')
        self.queue.put('STOP')

    def listener(self):
        """The server main loop, listen for and serve requests.

        When called, this method will receive and respond until there are no
        more messages then break to the caller.

        """
        # Note: we are using CurveZMQ to secure the messages (see
        # self.curve_auth, self.socket.curve_...key etc.). We have set up
        # public-key cryptography on the ZMQ messaging and sockets, so
        # there is no need to encrypt messages ourselves before sending.
        while True:
            # process any commands passed to the listener by its parent process
            if self.queue.qsize():
                command = self.queue.get()
                if command == 'STOP':
                    break
                raise ValueError('Unknown command "%s"' % command)

            try:
                # Check for messages
                msg = self.socket.recv_string(zmq.NOBLOCK)
            except zmq.error.Again:
                # No messages, break to parent loop/caller.
                break
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
                import traceback
                response = encode_(
                    {
                        'error': {
                            'message': 'failed to decode message: "%s"' % msg,
                            'traceback': traceback.format_exc(),
                        }
                    }
                ).encode()
            else:
                # success case - serve the request
                res = self.server.receiver(message)
                # send back the string to bytes response
                if isinstance(res.get('data'), bytes):
                    response = res['data']
                else:
                    response = encode_(res).encode()
            self.socket.send(response)

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
"""Publisher for suite runtime API."""

from threading import Thread

import zmq

from cylc.flow import LOG
from cylc.flow.exceptions import CylcError
from cylc.flow.ws_messages_pb2 import PbEntireWorkflow
from cylc.flow import __version__ as CYLC_VERSION

# maps server methods to the protobuf message (for client/UIS import)
PB_METHOD_MAP = {
    'pb_entire_workflow': PbEntireWorkflow
}


class WorkflowPublisher:
    """Initiate the PUB part of a ZMQ PUB-SUB pair.

    This class contains the logic for the ZMQ message Publisher.

    Note: Security TODO

    Usage:
        * Define ...

    """
    # TODO: Security will be provided by zmq.auth (post PR #3359)

    def __init__(self, context=None):
        if context is None:
            self.context = zmq.Context()
        else:
            self.context = context
        self.port = None
        self.socket = None
        self.endpoints = None
        self.thread = None

    def start(self, min_port, max_port):
        """Start the ZeroMQ publisher.

        Will use a port range provided to select random ports.

        Args:
            min_port (int): minimum socket port number
            max_port (int): maximum socket port number
        """
        # Context are thread safe, but Sockets are not so if multiple
        # sockets then they need be created on their own thread.
        self.thread = Thread(
            target=self._create_socket,
            args=(min_port, max_port)
        )
        self.thread.start()

    def _create_socket(self, min_port, max_port):
        """Create ZeroMQ Publish socket."""
        self.socket = self.context.socket(zmq.PUB)
        # this limit on messages in queue is more than enough,
        # as messages correspond to scheduler loops (*messages/loop):
        self.socket.sndhwm = 1000

        try:
            if min_port == max_port:
                self.port = min_port
                self.socket.bind('tcp://*:%d' % min_port)
            else:
                self.port = self.socket.bind_to_random_port(
                    'tcp://*', min_port, max_port)
        except (zmq.error.ZMQError, zmq.error.ZMQBindError) as exc:
            self.socket.close()
            raise CylcError(
                'could not start Cylc ZMQ publisher: %s' % str(exc))

    def stop(self):
        """Stop the publisher socket."""
        LOG.debug('stopping zmq publisher...')
        self.thread.join()
        self.socket.close()
        LOG.debug('...stopped')

    def publish(self, data, serializer=None):
        """Publish data."""
        try:
            if callable(serializer):
                self.socket.send(serializer(data))
            elif isinstance(serializer, str):
                self.socket.send(getattr(data, serializer)())
            else:
                self.socket.send(data)
        except Exception as exc:
            LOG.error('publisher: %s' % str(exc))

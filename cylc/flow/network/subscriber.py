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
"""Subscriber for published suite output."""

import sys
import json

import zmq
import zmq.asyncio


# we should only have one ZMQ context per-process
CONTEXT = zmq.asyncio.Context()


class WorkflowSubscriber:
    """Initiate the SUB part of a ZMQ PUB-SUB pair.

    This class contains the logic for the ZMQ message Subscriber.

    NOTE: Security to be provided by zmq.auth

    Args:
        host (str):
            The host to connect to.
        port (int):
            The port on the aforementioned host to connect to.

    Usage:
        * Subscribe to Publisher socket using ``WorkflowSubscriber.__call__``.

    """

    DEFAULT_TIMEOUT = 300.  # 5 min

    def __init__(self, host, port, timeout=None):
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        else:
            timeout = float(timeout)
        self.timeout = timeout * 1000

        # open the ZMQ socket
        self.socket = CONTEXT.socket(zmq.SUB)
        self.socket.connect(f'tcp://{host}:{port}')
        # if there is no server don't keep the subscriber hanging around
        self.socket.setsockopt(zmq.LINGER, int(timeout))

        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

    async def subscribe(self, msg_handler=None):
        """Subscribe to updates from the provided socket."""
        while True:
            msg = await self.socket.recv()
            if callable(msg_handler):
                msg_handler(msg)
            else:
                data = json.loads(msg)
                sys.stdout.write(
                    json.dumps(data, indent=4) + '\n')

    def stop(self):
        """Close subscriber socket."""
        self.socket.close()

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

import asyncio
import sys
import json

import zmq
import zmq.asyncio

from cylc.flow.ws_data_mgr import DELTAS_MAP


def process_delta_msg(btopic, delta_msg, func, *args, **kwargs):
    """Utility for processing serialised data-store deltas."""
    topic = btopic.decode('utf-8')
    try:
        delta = DELTAS_MAP[topic]()
    except KeyError:
        return
    delta.ParseFromString(delta_msg)
    func(topic, delta, *args, **kwargs)


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

    def __init__(self, host, port, context=None, topics=None, timeout=None):
        # we should only have one ZMQ context per-process
        # don't instantiate a client unless none passed in
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        if context is None:
            self.context = zmq.asyncio.Context()
        else:
            self.context = context
        if topics is None:
            topics = [b'']
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        else:
            timeout = float(timeout)
        self.timeout = timeout * 1000

        # open the ZMQ socket
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(f'tcp://{host}:{port}')
        # if there is no server don't keep the subscriber hanging around
        self.socket.setsockopt(zmq.LINGER, int(timeout))
        for topic in set(topics):
            self.socket.setsockopt(zmq.SUBSCRIBE, topic)

    async def subscribe(self, msg_handler, *args, **kwargs):
        """Subscribe to updates from the provided socket."""
        while True:
            if self.socket.closed:
                break
            try:
                [topic, msg] = await self.socket.recv_multipart()
            except zmq.error.ZMQError:
                continue
            if callable(msg_handler):
                msg_handler(topic, msg, *args, **kwargs)
            else:
                data = json.loads(msg)
                sys.stdout.write(
                    json.dumps(data, indent=4) + '\n')
        sleep(0)

    def stop(self):
        """Close subscriber socket."""
        self.socket.close()

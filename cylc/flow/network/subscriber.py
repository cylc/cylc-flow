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
"""Subscriber for published workflow output."""

import asyncio
import json
import sys
from typing import TYPE_CHECKING, Iterable, Optional, Set, Union

import zmq

from cylc.flow.data_store_mgr import DELTAS_MAP
from cylc.flow.network.base import ZMQSocketBase
from cylc.flow.network.util import get_location

if TYPE_CHECKING:
    import zmq.asyncio

NO_RECEIVE_INTERVAL = 0.5


def process_delta_msg(btopic, delta_msg, func, *args, **kwargs):
    """Utility for processing serialised data-store deltas."""
    topic = btopic.decode('utf-8')
    try:
        delta = DELTAS_MAP[topic]()
        delta.ParseFromString(delta_msg)
    except KeyError:
        delta = delta_msg
    if callable(func):
        return func(topic, delta, *args, **kwargs)
    return (topic, delta)


class WorkflowSubscriber(ZMQSocketBase):
    """Initiate the SUB part of a ZMQ PUB-SUB pair.

    This class contains the logic for the ZMQ message Subscriber.

    NOTE: Security to be provided by zmq.auth

    Args:
        host: The host to connect to.
        port: The port on the aforementioned host to connect to.

    Usage:
        * Subscribe to Publisher socket using ``WorkflowSubscriber.__call__``.

    """
    # socket & event loop not None - get assigned on init by self.start():
    socket: 'zmq.asyncio.Socket'
    loop: asyncio.AbstractEventLoop

    def __init__(
        self,
        workflow: str,
        host: Optional[str] = None,
        port: Union[int, str, None] = None,
        context: Optional['zmq.asyncio.Context'] = None,
        srv_public_key_loc: Optional[str] = None,
        topics: Optional[Iterable[bytes]] = None
    ):
        super().__init__(zmq.SUB, workflow, context=context)
        if port:
            port = int(port)
        if not (host and port):
            host, _, port = get_location(workflow)
        if topics is None:
            topics = {b''}
        self.topics: Set[bytes] = set(topics)
        # Connect the ZMQ socket on instantiation
        self.start(host, port, srv_public_key_loc)

    def _socket_options(self) -> None:
        """Set options after socket instantiation and before connect.

        Overwrites Base method.

        """
        # setup topics to receive.
        for topic in self.topics:
            self.socket.setsockopt(zmq.SUBSCRIBE, topic)

    async def subscribe(self, msg_handler, *args, **kwargs):
        """Subscribe to updates from the provided socket."""
        while True:
            if self.stopping:
                break
            try:
                [topic, msg] = await self.socket.recv_multipart(
                    flags=zmq.NOBLOCK)
            except zmq.ZMQError:
                await asyncio.sleep(NO_RECEIVE_INTERVAL)
                continue
            if callable(msg_handler):
                msg_handler(topic, msg, *args, **kwargs)
            else:
                data = json.loads(msg)
                sys.stdout.write(
                    json.dumps(data, indent=4) + '\n')

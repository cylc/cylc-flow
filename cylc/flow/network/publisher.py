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
"""Publisher for workflow runtime API."""

import asyncio
from typing import Callable, Optional, Set, TYPE_CHECKING, Union

import zmq

from cylc.flow import LOG
from cylc.flow.network import ZMQSocketBase


if TYPE_CHECKING:
    from zmq.asyncio import Context


def serialize_data(
    data: object, serializer: Union[Callable, str, None], *args, **kwargs
):
    """Serialize by specified method."""
    if callable(serializer):
        return serializer(data, *args, **kwargs)
    if isinstance(serializer, str):
        return getattr(data, serializer)(*args, **kwargs)
    return data


class WorkflowPublisher(ZMQSocketBase):
    """Initiate the PUB part of a ZMQ PUB-SUB pair.

    This class contains the logic for the ZMQ message Publisher.

    Usage:
        * Call publish to send items to subscribers.

    """

    def __init__(self, workflow: str, context: 'Optional[Context]' = None):
        super().__init__(zmq.PUB, workflow, bind=True, context=context)
        self.topics: Set[bytes] = set()

    def _socket_options(self):
        """Set socket options after socket instantiation and before bind.

        Overwrites Base method.

        """
        # this limit on messages in queue is more than enough,
        # as messages correspond to scheduler loops (*messages/loop):
        self.socket.sndhwm = 1000

    def _bespoke_stop(self):
        """Bespoke stop items."""
        LOG.debug('stopping zmq publisher...')
        self.stopping = True

    async def send_multi(
        self,
        topic: bytes,
        data: object,
        serializer: Union[Callable, str, None] = None
    ) -> None:
        """Send multi part message.

        Args:
            topic: The topic of the message.
            data: Data element/message to serialise and send.
            serializer: string/func for encoding.

        """
        if self.socket:
            self.topics.add(topic)
            self.socket.send_multipart(
                [topic, serialize_data(data, serializer)]
            )
        # else we are in the process of shutting down - don't send anything

    async def publish(self, *items: tuple) -> None:
        """Publish topics.

        Args:
            items (iterable): [(topic, data, serializer)]

        """
        try:
            await asyncio.gather(
                *(self.send_multi(*item) for item in items)
            )
        except Exception as exc:
            LOG.exception(f"publish: {exc}")

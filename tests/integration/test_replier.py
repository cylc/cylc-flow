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

import asyncio

from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.network.util import decode_

from async_timeout import timeout
import pytest


async def test_listener(one, start, ):
    """Test listener."""
    async with start(one):
        client = WorkflowRuntimeClient(one.workflow)
        client.socket.send_string(r'Not JSON')
        res = await client.socket.recv()
        assert 'error' in decode_(res.decode())

        one.server.replier.queue.put('STOP')
        async with timeout(2):
            # wait for the server to consume the STOP item from the queue
            while True:
                if one.server.replier.queue.empty():
                    break
                await asyncio.sleep(0.01)
        # ensure the server is "closed"
        one.server.replier.queue.put('foobar')
        with pytest.raises(ValueError):
            one.server.replier.listener()

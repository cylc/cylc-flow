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
import getpass
import sys

import pytest

from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.network import deserialize
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.scheduler import Scheduler


if sys.version_info[:2] >= (3, 11):
    from asyncio import timeout
else:
    from async_timeout import timeout


async def test_listener(one: Scheduler, start):
    """Test listener."""
    async with start(one):
        # Test listener handles an invalid message from client
        # (without directly calling listener):
        client = WorkflowRuntimeClient(one.workflow)
        client.socket.send_string(r'Not JSON')
        res = deserialize(
            (await client.socket.recv()).decode()
        )
        assert res['error']
        assert 'data' not in res
        # Check other fields are present:
        assert res['cylc_version'] == CYLC_VERSION
        assert res['user'] == getpass.getuser()

        one.server.replier.queue.put('STOP')
        async with timeout(2):
            # wait for the server to consume the STOP item from the queue
            while not one.server.replier.queue.empty():
                await asyncio.sleep(0.01)
        # ensure the server is "closed"
        one.server.replier.queue.put('foobar')
        with pytest.raises(ValueError):
            one.server.replier.listener()

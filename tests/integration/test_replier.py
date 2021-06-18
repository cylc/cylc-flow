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

from async_timeout import timeout
import asyncio
from getpass import getuser

import pytest


@pytest.mark.asyncio
@pytest.fixture(scope='module')
async def myflow(mod_flow, mod_scheduler, mod_run, mod_one_conf):
    reg = mod_flow(mod_one_conf)
    schd = mod_scheduler(reg)
    async with mod_run(schd):
        yield schd


@pytest.mark.asyncio
@pytest.fixture
async def accident(flow, scheduler, run, one_conf):
    reg = flow(one_conf)
    schd = scheduler(reg)
    async with run(schd):
        yield schd


@pytest.mark.asyncio
async def test_listener(accident):
    """Test listener."""
    accident.server.replier.queue.put('STOP')
    async with timeout(2):
        # wait for the server to consume the STOP item from the queue
        while True:
            if accident.server.replier.queue.empty():
                break
            await asyncio.sleep(0.01)
    # ensure the server is "closed"
    with pytest.raises(ValueError):
        accident.server.replier.queue.put('foobar')
        accident.server.replier._listener()

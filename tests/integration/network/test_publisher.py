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

from cylc.flow.network.subscriber import (
    WorkflowSubscriber,
    process_delta_msg
)


async def test_publisher(flow, scheduler, run, one_conf, port_range):
    """It should publish deltas when the flow starts."""
    id_ = flow(one_conf)
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # create a subscriber
        subscriber = WorkflowSubscriber(
            schd.workflow,
            host=schd.host,
            port=schd.server.pub_port,
            topics=[b'workflow']
        )

        async with timeout(2):
            # wait for the first delta from the workflow
            btopic, msg = await subscriber.socket.recv_multipart()

        _, delta = process_delta_msg(btopic, msg, None)
        for key in ('added', 'updated'):
            if getattr(getattr(delta, key), 'id', None):
                assert schd.id == getattr(delta, key).id
                break
        else:
            raise Exception("Delta wasn't added or updated")

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
import io
import json
from contextlib import redirect_stdout

from cylc.flow.network.subscriber import (
    WorkflowSubscriber,
    process_delta_msg,
)


def bespoke_encoder(data):
    return data.encode('utf-8')


async def test_subscriber(flow, scheduler, run, one_conf, port_range):
    """It should recieve publish deltas when the flow starts."""
    id_ = flow(one_conf)
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # create a subscriber
        subscriber = WorkflowSubscriber(
            schd.workflow,
            host=schd.host,
            port=schd.server.pub_port,
            topics=[b'shutdown']
        )

        subscriber.unsubscribe_topic(b'shutdown')
        # test unsubscribe non-subscribed
        subscriber.unsubscribe_topic(b'workflow')
        assert subscriber.topics == set()
        subscriber.subscribe_topic(b'workflow')
        # test subscribe to already-subscribed
        subscriber.subscribe_topic(b'workflow')
        assert subscriber.topics == {b'workflow'}

        # create a subscriber2 with no specified host/port and
        # a bespoke topic/message
        subscriber2 = WorkflowSubscriber(
            schd.workflow,
            topics=[b'bespoke']
        )
        bespoke_msg = {'this': 'that'}
        bespoke_json = json.dumps(bespoke_msg, indent=4)
        await schd.server.publisher.publish(
            *[(b'bespoke', bespoke_json, bespoke_encoder)]
        )

        async with asyncio.timeout(2):
            # wait for the first delta from the workflow
            btopic, msg = await subscriber.socket.recv_multipart()
            # get the published bespoke msg
            f = io.StringIO()
            with redirect_stdout(f):
                subscriber2.stopping = True
                await subscriber2.subscribe(msg_handler=None)
        # test the default message handling
        assert f.getvalue() == bespoke_json + '\n'

        _, delta = process_delta_msg(btopic, msg, None)
        for key in ('added', 'updated'):
            if getattr(getattr(delta, key), 'id', None):
                assert schd.id == getattr(delta, key).id
                break
        else:
            raise Exception("Delta wasn't added or updated")

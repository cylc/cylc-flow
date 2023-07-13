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

from typing import Callable
from async_timeout import timeout
from getpass import getuser

import pytest

from cylc.flow.network.server import PB_METHOD_MAP
from cylc.flow.scheduler import Scheduler


@pytest.fixture(scope='module')
async def myflow(mod_flow, mod_scheduler, mod_run, mod_one_conf):
    id_ = mod_flow(mod_one_conf)
    schd = mod_scheduler(id_)
    async with mod_run(schd):
        yield schd


def run_server_method(schd, method, *args, **kwargs):
    kwargs['user'] = getuser()
    return getattr(schd.server, method)(*args, **kwargs)


def call_server_method(method, *args, **kwargs):
    kwargs['user'] = getuser()
    return method(*args, **kwargs)


def test_graphql(myflow):
    """Test GraphQL endpoint method."""
    request_string = f'''
        query {{
            workflows(ids: ["{myflow.id}"]) {{
                id
            }}
        }}
    '''
    data = call_server_method(myflow.server.graphql, request_string)
    assert myflow.id == data['workflows'][0]['id']


def test_pb_data_elements(myflow):
    """Test Protobuf elements endpoint method."""
    element_type = 'workflow'
    data = PB_METHOD_MAP['pb_data_elements'][element_type]()
    data.ParseFromString(
        call_server_method(
            myflow.server.pb_data_elements,
            element_type
        )
    )
    assert data.added.id == myflow.id


def test_pb_entire_workflow(myflow):
    """Test Protobuf entire workflow endpoint method."""
    data = PB_METHOD_MAP['pb_entire_workflow']()
    data.ParseFromString(
        call_server_method(
            myflow.server.pb_entire_workflow
        )
    )
    assert data.workflow.id == myflow.id


async def test_stop(one: Scheduler, start):
    """Test stop."""
    async with start(one):
        async with timeout(2):
            # Wait for the server to consume the STOP signal.
            # If it doesn't, the test will fail with a timeout error.
            await one.server.stop('TESTING')
            assert one.server.stopped


async def test_receiver(one: Scheduler, start):
    """Test the receiver with different message objects."""
    async with timeout(5):
        async with start(one):
            # start with a message that works
            msg = {'command': 'api', 'user': '', 'args': {}}
            assert 'error' not in one.server.receiver(msg)
            assert 'data' in one.server.receiver(msg)

            # remove the user field - should error
            msg2 = dict(msg)
            msg2.pop('user')
            assert 'error' in one.server.receiver(msg2)

            # remove the command field - should error
            msg3 = dict(msg)
            msg3.pop('command')
            assert 'error' in one.server.receiver(msg3)

            # provide an invalid command - should error
            msg4 = {**msg, 'command': 'foobar'}
            assert 'error' in one.server.receiver(msg4)

            # simulate a command failure with the original message
            # (the one which worked earlier) - should error
            def _api(*args, **kwargs):
                raise Exception('foo')
            one.server.api = _api
            assert 'error' in one.server.receiver(msg)


async def test_publish_before_shutdown(
    one: Scheduler, start: Callable
):
    """Test that the server publishes final deltas before shutting down."""
    async with start(one):
        one.server.publish_queue.put([(b'fake', b'blah')])
        await one.server.stop('i said stop!')
        assert not one.server.publish_queue.qsize()

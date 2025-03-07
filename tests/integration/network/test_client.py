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

"""Test cylc.flow.client.WorkflowRuntimeClient."""
import json
from unittest.mock import Mock
import pytest

from cylc.flow.exceptions import ClientError
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.network.server import PB_METHOD_MAP


@pytest.fixture(scope='module')
async def harness(mod_flow, mod_scheduler, mod_run, mod_one_conf):
    id_ = mod_flow(mod_one_conf)
    schd = mod_scheduler(id_)
    async with mod_run(schd):
        client = WorkflowRuntimeClient(id_)
        yield schd, client


async def test_graphql(harness):
    """It should return True if running."""
    schd, client = harness
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { workflows { id } }'}
    )
    workflows = ret['workflows']
    assert len(workflows) == 1
    workflow = workflows[0]
    assert schd.workflow in workflow['id']


async def test_protobuf(harness):
    """It should return True if running."""
    schd, client = harness
    ret = await client.async_request('pb_entire_workflow')
    pb_data = PB_METHOD_MAP['pb_entire_workflow']()
    pb_data.ParseFromString(ret)
    assert schd.workflow in pb_data.workflow.id


async def test_command_validation_failure(harness):
    """It should send the correct response if a command fails validation.

    Command arguments are validated before the command is queued. Any issues at
    this stage will be communicated back via the mutation "result".

    See https://github.com/cylc/cylc-flow/pull/6112
    """
    schd, client = harness

    # run a mutation that will fail validation
    response = await client.async_request(
        'graphql',
        {
            'request_string': '''
                 mutation {
                   set(
                     workflows: ["*"],
                     tasks: ["*"],
                     # this list of prerequisites fails validation:
                     prerequisites: ["1/a", "all"]
                   ) {
                     result
                   }
                 }
        '''
        },
    )

    # the validation error should be returned to the client
    assert response['set']['result'] == [
        {
            'id': schd.id,
            'response': [False, '--pre=all must be used alone'],
        }
    ]


@pytest.mark.parametrize(
    'sock_response, expected',
    [
        pytest.param({'error': 'message'}, r"^message$", id="basic"),
        pytest.param(
            {'foo': 1},
            r"^Received invalid response for"
            r" Cylc 8\.[\w.]+: \{'foo': 1[^}]*\}$",
            id="no-err-field",
        ),
        pytest.param(
            {'cylc_version': '8.x.y'},
            r"^Received invalid.+\n\(Workflow is running in Cylc 8.x.y\)$",
            id="no-err-field-with-version",
        ),
    ],
)
async def test_async_request_err(
    one, start, monkeypatch: pytest.MonkeyPatch, sock_response, expected
):
    async def mock_recv():
        return json.dumps(sock_response).encode()

    async with start(one):
        client = WorkflowRuntimeClient(one.workflow)
        with monkeypatch.context() as mp:
            mp.setattr(client, 'socket', Mock(recv=mock_recv))
            mp.setattr(client, 'poller', Mock())

            with pytest.raises(ClientError, match=expected):
                await client.async_request('graphql')

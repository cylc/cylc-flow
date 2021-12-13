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
import pytest
from typing import Optional, Union
from unittest.mock import Mock

from cylc.flow.exceptions import ClientError, ClientTimeout
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.network.server import PB_METHOD_MAP


def async_return(value):
    """Return an awaitable that returns ``value``."""
    async def _async_return():
        return value
    return _async_return


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
    workflows = ret['data']['workflows']
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
                        results {
                            workflowId
                            success
                            message
                        }
                    }
                }
        '''
        },
    )

    # the validation error should be returned to the client
    assert response['data']['set']['results'] == [
        {
            'workflowId': schd.id,
            'success': False,
            'message': '--pre=all must be used alone',
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'cmd, timeout, mock_response, expected',
    [
        pytest.param(
            'graphql',
            False,
            b'[{"ringbearer": "frodo"}, null, null]',
            {"ringbearer": "frodo"},
            id="Normal graphql"
        ),
        pytest.param(
            'pb_entire_workflow',
            False,
            b'mock protobuf response',
            b'mock protobuf response',
            id="Normal PB"
        ),
        pytest.param(
            'graphql',
            True,
            None,
            ClientTimeout("blah"),
            id="Timeout"
        ),
        pytest.param(
            'graphql',
            False,
            b'[null, ["mock error msg", "mock traceback"], null]',
            ClientError("mock error msg", "mock traceback"),
            id="Client error"
        ),
        pytest.param(
            'graphql',
            False,
            b'[null, null, null]',
            ClientError("No response from server. Check the workflow log."),
            id="Empty response"
        ),
    ]
)
async def test_async_request(
    cmd: str,
    timeout: bool,
    mock_response: Optional[bytes],
    expected: Union[bytes, object, Exception],
    harness,
    monkeypatch: pytest.MonkeyPatch
):
    """Test structure of date sent/received by
    WorkflowRuntimeClient.async_request()

    Params:
        cmd: Network command to be tested.
        timeout: Whether to simulate a client timeout.
        mock_response: Simulated response from the server.
        expected: Expected return value, or an Exception expected to be raised.
    """
    client: WorkflowRuntimeClient
    _, client = harness
    mock_socket = Mock()
    mock_socket.recv.side_effect = async_return(mock_response)
    monkeypatch.setattr(client, 'socket', mock_socket)
    mock_poller = Mock()
    mock_poller.poll.return_value = not timeout
    monkeypatch.setattr(client, 'poller', mock_poller)

    args = {}  # type: ignore[var-annotated]
    expected_msg = {'command': cmd, 'args': args, **client.header}

    call = client.async_request(cmd, args)
    if isinstance(expected, Exception):
        with pytest.raises(type(expected)) as ei:
            await call
        if isinstance(expected, ClientError):
            assert ei.value.args == expected.args
    else:
        assert await call == expected
    mock_socket.send_string.assert_called_with(json.dumps(expected_msg))

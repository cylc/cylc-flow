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
import pytest

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

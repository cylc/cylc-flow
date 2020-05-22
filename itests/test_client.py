"""Test cylc.flow.client.SuiteRuntimeClient."""
import pytest

from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.network.server import PB_METHOD_MAP


@pytest.mark.asyncio
async def test_ping(simple_conf, flow, run_flow):
    """It should return True if running."""
    scheduler = flow(simple_conf)
    async with run_flow(scheduler):
        client = SuiteRuntimeClient(scheduler.suite)
        assert await client.async_request('ping_suite')
        assert not client.socket.closed


@pytest.mark.asyncio
async def test_graphql(simple_conf, flow, run_flow):
    """It should return True if running."""
    scheduler = flow(simple_conf)
    async with run_flow(scheduler):
        client = SuiteRuntimeClient(scheduler.suite)
        ret = await client.async_request(
            'graphql',
            {'request_string': 'query { workflows { id } }'}
        )
        workflows = ret['workflows']
        assert len(workflows) == 1
        workflow = workflows[0]
        assert scheduler.suite in workflow['id']


@pytest.mark.asyncio
async def test_protobuf(simple_conf, flow, run_flow):
    """It should return True if running."""
    scheduler = flow(simple_conf)
    async with run_flow(scheduler):
        client = SuiteRuntimeClient(scheduler.suite)
        ret = await client.async_request('pb_entire_workflow')
        pb_data = PB_METHOD_MAP['pb_entire_workflow']()
        pb_data.ParseFromString(ret)
        assert scheduler.suite in pb_data.workflow.id

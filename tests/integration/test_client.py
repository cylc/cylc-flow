"""Test cylc.flow.client.SuiteRuntimeClient."""
import pytest

from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.network.server import PB_METHOD_MAP


@pytest.mark.asyncio
@pytest.fixture(scope='module')
async def harness(mod_flow, mod_scheduler, mod_run, mod_one_conf):
    reg = mod_flow(mod_one_conf)
    schd = mod_scheduler(reg)
    async with mod_run(schd):
        client = SuiteRuntimeClient(reg)
        yield schd, client


@pytest.mark.asyncio
@pytest.mark.skip('SuiteRuntimeClient uses a different loop?')
async def test_ping(harness):
    """It should return True if running."""
    _, client = harness
    assert await client.async_request('ping_suite')
    assert not client.socket.closed


@pytest.mark.asyncio
@pytest.mark.skip('SuiteRuntimeClient uses a different loop?')
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
    assert schd.suite in workflow['id']


@pytest.mark.asyncio
@pytest.mark.skip('SuiteRuntimeClient uses a different loop?')
async def test_protobuf(harness):
    """It should return True if running."""
    schd, client = harness
    ret = await client.async_request('pb_entire_workflow')
    pb_data = PB_METHOD_MAP['pb_entire_workflow']()
    pb_data.ParseFromString(ret)
    assert schd.suite in pb_data.workflow.id

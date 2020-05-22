import pytest

from cylc.flow.data_store_mgr import DELTAS_MAP
from cylc.flow.network.subscriber import WorkflowSubscriber


@pytest.mark.asyncio
async def test_publisher(flow, run_flow, simple_conf, port_range):
    """It should publish deltas when the flow starts."""
    scheduler = flow(simple_conf)
    async with run_flow(scheduler):
        # create a subscriber
        subscriber = WorkflowSubscriber(
            scheduler.suite,
            host=scheduler.host,
            port=scheduler.publisher.port,
            topics=[b'workflow']
        )
        # wait for the first delta from the workflow
        btopic, msg = await subscriber.socket.recv_multipart()
        delta = DELTAS_MAP[btopic.decode('utf-8')]()
        delta.ParseFromString(msg)
        # assert scheduler.suite in delta.id

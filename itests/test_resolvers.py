from unittest.mock import Mock

import pytest

from cylc.flow.data_store_mgr import (
    DataStoreMgr, ID_DELIM, EDGES, TASK_PROXIES, WORKFLOW
)
from cylc.flow.network.resolvers import node_filter, Resolvers
from cylc.flow.network.schema import parse_node_id


@pytest.fixture
def flow_args():
    return {
        'workflows': [],
        'exworkflows': [],
    }


@pytest.fixture
def node_args():
    return {
        'ghosts': False,
        'workflows': [],
        'exworkflows': [],
        'ids': [],
        'exids': [],
        'states': [],
        'exstates': [],
        'mindepth': -1,
        'maxdepth': -1,
    }


@pytest.fixture(scope='module')
async def flow(mod_flow, mod_run_flow):
    scheduler = mod_flow({
        'scheduling': {
            'initial cycle point': '2000',
            'dependencies': {
                'R1': 'prep => foo',
                'PT12H': 'foo[-PT12H] => foo => bar'
            }
        },
        # 'visualization': {
        #     'initial cycle point': '20130808T00',
        #     'final cycle point': '20130808T12'
        # }
    }, hold_start=True)
    ret = Mock()
    async with mod_run_flow(scheduler):
        ret.scheduler = scheduler
        ret.owner = scheduler.owner
        ret.name = scheduler.suite
        ret.id = list(scheduler.data_store_mgr.data.keys())[0]
        ret.resolvers = Resolvers(
            scheduler.data_store_mgr.data,
            schd=scheduler
        )
        ret.data = scheduler.data_store_mgr.data[ret.id]
        ret.node_ids = [
            node.id
            for node in ret.data[TASK_PROXIES].values()
        ]
        ret.edge_ids = [
            edge.id
            for edge in ret.data[EDGES].values()
        ]

        yield ret


@pytest.mark.asyncio
async def test_get_workflows(flow, flow_args):
    """Test method returning workflow messages satisfying filter args."""
    flow_args['workflows'].append((flow.owner, flow.name, None))
    flow_msgs = await flow.resolvers.get_workflows(flow_args)
    assert len(flow_msgs) == 1


@pytest.mark.asyncio
async def test_get_nodes_all(flow, node_args):
    """Test method returning workflow(s) node message satisfying filter args.
    """
    node_args['workflows'].append((flow.owner, flow.name, None))
    node_args['states'].append('failed')
    nodes = await flow.resolvers.get_nodes_all(TASK_PROXIES, node_args)
    # assert len(nodes) == 0

    # TODO - this results in traceback for some reason
    # node_args['ghosts'] = True
    # node_args['states'] = []
    # node_args['ids'].append(parse_node_id(flow.node_ids, TASK_PROXIES))
    # data = list(schd.data_store_mgr.data.values())[0]
    # nodes = [
    #     n
    #     for n in await resolvers.get_nodes_all(TASK_PROXIES, node_args)
    #     if n in data[TASK_PROXIES].values()
    # ]
    # assert len(nodes) == 1


@pytest.mark.asyncio
async def test_get_nodes_by_ids(flow, node_args):
    """Test method returning workflow(s) node messages
    who's ID is a match to any given."""
    node_args['workflows'].append((flow.owner, flow.name, None))
    nodes = await flow.resolvers.get_nodes_by_ids(TASK_PROXIES, node_args)
    assert len(nodes) == 0

    assert flow.scheduler.data_store_mgr.data == None

    node_args['ghosts'] = True
    node_args['native_ids'] = flow.node_ids
    nodes = [
        n
        for n in await flow.resolvers.get_nodes_by_ids(
            TASK_PROXIES, node_args
        )
        # if n in flow.data[TASK_PROXIES].values()
    ]
    assert len(nodes) > 0


@pytest.mark.asyncio
async def test_get_node_by_id(flow, node_args):
    """Test method returning a workflow node message
    who's ID is a match to that given."""
    node_args['id'] = f'me{ID_DELIM}mine{ID_DELIM}20500808T00{ID_DELIM}jin'
    node_args['workflows'].append((flow.owner, flow.name, None))
    node = await flow.resolvers.get_node_by_id(TASK_PROXIES, node_args)
    assert node is None
    node_args['id'] = flow.node_ids[0]
    node = await flow.resolvers.get_node_by_id(TASK_PROXIES, node_args)
    assert node in flow.data[TASK_PROXIES].values()


@pytest.mark.asyncio
async def test_get_edges_all(flow, flow_args):
    """Test method returning all workflow(s) edges."""
    edges = [
        e
        for e in await flow.resolvers.get_edges_all(flow_args)
        if e in flow.data[EDGES].values()
    ]
    assert len(edges) > 0


@pytest.mark.asyncio
async def test_get_edges_by_ids(flow, node_args):
    """Test method returning workflow(s) edge messages
    who's ID is a match to any given edge IDs."""
    edges = await flow.resolvers.get_edges_by_ids(node_args)
    assert len(edges) == 0
    node_args['native_ids'] = flow.edge_ids
    edges = [
        e
        for e in await flow.resolvers.get_edges_by_ids(node_args)
        if e in flow.data[EDGES].values()
    ]
    assert len(edges) > 0


# @pytest.mark.asyncio
# async def test_zzz(flow):
#     assert flow.data == []

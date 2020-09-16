# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
from unittest.mock import Mock

import pytest

from cylc.flow.data_store_mgr import ID_DELIM, EDGES, TASK_PROXIES
from cylc.flow.network.resolvers import Resolvers
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
async def flow(mod_flow, mod_scheduler, mod_run):
    ret = Mock()
    ret.reg = mod_flow({
        'scheduling': {
            'initial cycle point': '2000',
            'dependencies': {
                'R1': 'prep => foo',
                'PT12H': 'foo[-PT12H] => foo => bar'
            }
        }
    })

    ret.schd = mod_scheduler(ret.reg, hold_start=True)
    await ret.schd.install()
    await ret.schd.initialise()
    await ret.schd.configure()
    ret.schd.release_tasks()
    ret.schd.data_store_mgr.initiate_data_model()

    ret.owner = ret.schd.owner
    ret.name = ret.schd.suite
    ret.id = list(ret.schd.data_store_mgr.data.keys())[0]
    ret.resolvers = Resolvers(
        ret.schd.data_store_mgr,
        schd=ret.schd
    )
    ret.data = ret.schd.data_store_mgr.data[ret.id]
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
    assert len(nodes) == 0
    node_args['ghosts'] = True
    node_args['states'] = []
    node_args['ids'].append(parse_node_id(flow.node_ids[0], TASK_PROXIES))
    nodes = [
        n
        for n in await flow.resolvers.get_nodes_all(TASK_PROXIES, node_args)
        if n in flow.data[TASK_PROXIES].values()
    ]
    assert len(nodes) == 1


@pytest.mark.asyncio
async def test_get_nodes_by_ids(flow, node_args):
    """Test method returning workflow(s) node messages
    who's ID is a match to any given."""
    node_args['workflows'].append((flow.owner, flow.name, None))
    nodes = await flow.resolvers.get_nodes_by_ids(TASK_PROXIES, node_args)
    assert len(nodes) == 0

    node_args['ghosts'] = True
    node_args['native_ids'] = flow.node_ids
    nodes = [
        n
        for n in await flow.resolvers.get_nodes_by_ids(
            TASK_PROXIES, node_args
        )
        if n in flow.data[TASK_PROXIES].values()
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


@pytest.mark.asyncio
async def test_mutator(flow, flow_args):
    """Test the mutation method."""
    flow_args['workflows'].append((flow.owner, flow.name, None))
    args = {}
    response = await flow.resolvers.mutator(
        None,
        'hold',
        flow_args,
        args
    )
    assert response[0]['id'] == flow.id


@pytest.mark.skip(
    reason='TODO: trigger_tasks is resultin in traceback due to '
    'missing task_globs arg')
@pytest.mark.asyncio
async def test_nodes_mutator(flow, flow_args):
    """Test the nodes mutation method."""
    flow_args['workflows'].append((flow.owner, flow.name, None))
    args = {}
    ids = [parse_node_id(n, TASK_PROXIES) for n in flow.node_ids]
    response = await flow.resolvers.nodes_mutator(
        None, 'trigger_tasks', ids, flow_args, args
    )
    assert response[0]['id'] == flow.id


@pytest.mark.asyncio
async def test_mutation_mapper(flow):
    """Test the mapping of mutations to internal command methods."""
    response = await flow.resolvers._mutation_mapper('hold', {})
    assert response is not None

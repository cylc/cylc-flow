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
import pytest
from unittest.mock import Mock

from cylc.flow.data_store_mgr import ID_DELIM, EDGES, TASK_PROXIES
from cylc.flow.network.resolvers import Resolvers
from cylc.flow.network.schema import parse_node_id
from cylc.flow.scheduler import Scheduler


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
async def mock_flow(
    mod_flow: Callable[..., str],
    mod_scheduler: Callable[..., Scheduler]
) -> Scheduler:
    ret = Mock()
    ret.reg = mod_flow({
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'initial cycle point': '2000',
            'dependencies': {
                'R1': 'prep => foo',
                'PT12H': 'foo[-PT12H] => foo => bar'
            }
        }
    })

    ret.schd = mod_scheduler(ret.reg, paused_start=True)
    await ret.schd.install()
    await ret.schd.initialise()
    await ret.schd.configure()
    ret.schd.pool.release_runahead_tasks()
    ret.schd.data_store_mgr.initiate_data_model()

    ret.owner = ret.schd.owner
    ret.name = ret.schd.workflow
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

    return ret


@pytest.mark.asyncio
async def test_get_workflows(mock_flow, flow_args):
    """Test method returning workflow messages satisfying filter args."""
    flow_args['workflows'].append((mock_flow.owner, mock_flow.name, None))
    flow_msgs = await mock_flow.resolvers.get_workflows(flow_args)
    assert len(flow_msgs) == 1


@pytest.mark.asyncio
async def test_get_nodes_all(mock_flow, node_args):
    """Test method returning workflow(s) node message satisfying filter args.
    """
    node_args['workflows'].append((mock_flow.owner, mock_flow.name, None))
    node_args['states'].append('failed')
    nodes = await mock_flow.resolvers.get_nodes_all(TASK_PROXIES, node_args)
    assert len(nodes) == 0
    node_args['ghosts'] = True
    node_args['states'] = []
    node_args['ids'].append(parse_node_id(mock_flow.node_ids[0], TASK_PROXIES))
    nodes = [
        n for n in await mock_flow.resolvers.get_nodes_all(
            TASK_PROXIES, node_args)
        if n in mock_flow.data[TASK_PROXIES].values()
    ]
    assert len(nodes) == 1


@pytest.mark.asyncio
async def test_get_nodes_by_ids(mock_flow, node_args):
    """Test method returning workflow(s) node messages
    who's ID is a match to any given."""
    node_args['workflows'].append((mock_flow.owner, mock_flow.name, None))
    nodes = await mock_flow.resolvers.get_nodes_by_ids(TASK_PROXIES, node_args)
    assert len(nodes) == 0

    node_args['ghosts'] = True
    node_args['native_ids'] = mock_flow.node_ids
    nodes = [
        n
        for n in await mock_flow.resolvers.get_nodes_by_ids(
            TASK_PROXIES, node_args
        )
        if n in mock_flow.data[TASK_PROXIES].values()
    ]
    assert len(nodes) > 0


@pytest.mark.asyncio
async def test_get_node_by_id(mock_flow, node_args):
    """Test method returning a workflow node message
    who's ID is a match to that given."""
    node_args['id'] = f'me{ID_DELIM}mine{ID_DELIM}20500808T00{ID_DELIM}jin'
    node_args['workflows'].append((mock_flow.owner, mock_flow.name, None))
    node = await mock_flow.resolvers.get_node_by_id(TASK_PROXIES, node_args)
    assert node is None
    node_args['id'] = mock_flow.node_ids[0]
    node = await mock_flow.resolvers.get_node_by_id(TASK_PROXIES, node_args)
    assert node in mock_flow.data[TASK_PROXIES].values()


@pytest.mark.asyncio
async def test_get_edges_all(mock_flow, flow_args):
    """Test method returning all workflow(s) edges."""
    edges = [
        e
        for e in await mock_flow.resolvers.get_edges_all(flow_args)
        if e in mock_flow.data[EDGES].values()
    ]
    assert len(edges) > 0


@pytest.mark.asyncio
async def test_get_edges_by_ids(mock_flow, node_args):
    """Test method returning workflow(s) edge messages
    who's ID is a match to any given edge IDs."""
    edges = await mock_flow.resolvers.get_edges_by_ids(node_args)
    assert len(edges) == 0
    node_args['native_ids'] = mock_flow.edge_ids
    edges = [
        e
        for e in await mock_flow.resolvers.get_edges_by_ids(node_args)
        if e in mock_flow.data[EDGES].values()
    ]
    assert len(edges) > 0


@pytest.mark.asyncio
async def test_mutator(mock_flow, flow_args):
    """Test the mutation method."""
    flow_args['workflows'].append((mock_flow.owner, mock_flow.name, None))
    args = {}
    response = await mock_flow.resolvers.mutator(
        None,
        'pause',
        flow_args,
        args
    )
    assert response[0]['id'] == mock_flow.id


@pytest.mark.asyncio
async def test_nodes_mutator(mock_flow, flow_args):
    """Test the nodes mutation method."""
    flow_args['workflows'].append((mock_flow.owner, mock_flow.name, None))
    ids = [parse_node_id(n, TASK_PROXIES) for n in mock_flow.node_ids]
    response = await mock_flow.resolvers.nodes_mutator(
        None, 'force_trigger_tasks', ids, flow_args,
        {"reflow": False, "flow_descr": ""}
    )
    assert response[0]['id'] == mock_flow.id


@pytest.mark.asyncio
async def test_mutation_mapper(mock_flow):
    """Test the mapping of mutations to internal command methods."""
    response = await mock_flow.resolvers._mutation_mapper('pause', {})
    assert response is not None

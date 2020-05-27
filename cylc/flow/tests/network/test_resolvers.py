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

from unittest import main
from copy import deepcopy
import asyncio

from cylc.flow import ID_DELIM
from cylc.flow.tests.util import CylcWorkflowTestCase, create_task_proxy
from cylc.flow.data_store_mgr import (
    DataStoreMgr, EDGES, TASK_PROXIES, WORKFLOW
)
from cylc.flow.network.schema import parse_node_id
from cylc.flow.network.resolvers import node_filter, Resolvers


def _run_coroutine(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


FLOW_ARGS = {
    'workflows': [],
    'exworkflows': [],
}


NODE_ARGS = {
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


class FakeFlow:
    owner = 'qux'
    name = 'baz'
    status = 'running'


class FakeNode:
    id = f'qux{ID_DELIM}baz{ID_DELIM}20130808T00{ID_DELIM}foo{ID_DELIM}1'
    namespace = ['root', 'foo']
    name = 'foo'
    cycle_point = '20130808T00'
    state = 'running'
    submit_num = 1


def test_node_filter():
    node = FakeNode()
    args = deepcopy(NODE_ARGS)
    args['ids'].append(('*', '*', '*', 'foo', '01', 'failed'))
    assert not node_filter(node, args)
    args['ids'].append(('*', '*', '*', 'foo', '01', 'running'))
    args['states'].append('running')
    assert node_filter(node, args)


class TestResolvers(CylcWorkflowTestCase):

    suite_name = "five"
    suiterc = """
[meta]
    title = "Inter-cycle dependence + a cold-start task"
[cylc]
    UTC mode = True
[scheduling]
    #runahead limit = 120
    initial cycle point = 20130808T00
    final cycle point = 20130812T00
    [[graph]]
        R1 = "prep => foo"
        PT12H = "foo[-PT12H] => foo => bar"
[visualization]
    initial cycle point = 20130808T00
    final cycle point = 20130808T12
    [[node attributes]]
        foo = "color=red"
        bar = "color=blue"

    """

    def setUp(self) -> None:
        super(TestResolvers, self).setUp()
        self.scheduler.data_store_mgr = DataStoreMgr(self.scheduler)
        for name in self.scheduler.config.taskdefs:
            task_proxy = create_task_proxy(
                task_name=name,
                suite_config=self.suite_config,
                is_startup=True
            )
            warnings = self.task_pool.insert_tasks(
                items=[task_proxy.identity],
                stopcp=None,
                check_point=True
            )
            assert 0 == warnings
        self.task_pool.release_runahead_tasks()
        self.scheduler.data_store_mgr.initiate_data_model()
        self.workflow_id = self.scheduler.data_store_mgr.workflow_id
        self.data = self.scheduler.data_store_mgr.data[self.workflow_id]
        self.node_ids = [
            node.id
            for node in self.data[TASK_PROXIES].values()]
        self.edge_ids = [
            edge.id
            for edge in self.data[EDGES].values()]
        self.resolvers = Resolvers(
            self.scheduler.data_store_mgr.data,
            schd=self.scheduler)

    def test_constructor(self):
        self.assertIsNotNone(self.resolvers.schd)

    def test_get_workflows(self):
        """Test method returning workflow messages satisfying filter args."""
        args = deepcopy(FLOW_ARGS)
        args['workflows'].append((self.owner, self.suite_name, None))
        flow_msgs = _run_coroutine(self.resolvers.get_workflows(args))
        self.assertEqual(1, len(flow_msgs))

    def test_get_nodes_all(self):
        """Test method returning workflow(s) node messages
        satisfying filter args."""
        args = deepcopy(NODE_ARGS)
        args['workflows'].append((self.owner, self.suite_name, None))
        args['states'].append('failed')
        nodes = _run_coroutine(
            self.resolvers.get_nodes_all(TASK_PROXIES, args))
        self.assertEqual(0, len(nodes))
        args['ghosts'] = True
        args['states'] = []
        args['ids'].append(parse_node_id(self.node_ids[0], TASK_PROXIES))
        nodes = [
            n
            for n in _run_coroutine(
                self.resolvers.get_nodes_all(TASK_PROXIES, args))
            if n in self.data[TASK_PROXIES].values()]
        self.assertEqual(1, len(nodes))

    def test_get_nodes_by_ids(self):
        """Test method returning workflow(s) node messages
        who's ID is a match to any given."""
        args = deepcopy(NODE_ARGS)
        args['workflows'].append((self.owner, self.suite_name, None))
        nodes = _run_coroutine(
            self.resolvers.get_nodes_by_ids(TASK_PROXIES, args))
        self.assertEqual(0, len(nodes))
        args['ghosts'] = True
        args['native_ids'] = self.node_ids
        nodes = [
            n
            for n in _run_coroutine(
                self.resolvers.get_nodes_by_ids(TASK_PROXIES, args))
            if n in self.data[TASK_PROXIES].values()]
        self.assertTrue(len(nodes) > 0)

    def test_get_node_by_id(self):
        """Test method returning a workflow node message
        who's ID is a match to that given."""
        args = deepcopy(NODE_ARGS)
        args['id'] = f'me{ID_DELIM}mine{ID_DELIM}20500808T00{ID_DELIM}jin'
        args['workflows'].append((self.owner, self.suite_name, None))
        node = _run_coroutine(
            self.resolvers.get_node_by_id(TASK_PROXIES, args))
        self.assertIsNone(node)
        args['id'] = self.node_ids[0]
        node = _run_coroutine(
            self.resolvers.get_node_by_id(TASK_PROXIES, args))
        self.assertTrue(
            node in self.data[TASK_PROXIES].values())

    def test_get_edges_all(self):
        """Test method returning all workflow(s) edges."""
        edges = [
            e
            for e in _run_coroutine(self.resolvers.get_edges_all(FLOW_ARGS))
            if e in self.data[EDGES].values()]
        self.assertTrue(len(edges) > 0)

    def test_get_edges_by_ids(self):
        """Test method returning workflow(s) edge messages
        who's ID is a match to any given edge IDs."""
        args = deepcopy(NODE_ARGS)
        edges = _run_coroutine(self.resolvers.get_edges_by_ids(args))
        self.assertEqual(0, len(edges))
        args['native_ids'] = self.edge_ids
        edges = [
            e
            for e in _run_coroutine(self.resolvers.get_edges_by_ids(args))
            if e in self.data[EDGES].values()]
        self.assertTrue(len(edges) > 0)

    def test_mutator(self):
        """Test the mutation method."""
        w_args = deepcopy(FLOW_ARGS)
        w_args['workflows'].append((self.owner, self.suite_name, None))
        args = {}
        response = _run_coroutine(
            self.resolvers.mutator(None, 'hold_suite', w_args, args))
        self.assertEqual(response[0]['id'], self.workflow_id)

    def test_nodes_mutator(self):
        """Test the nodes mutation method."""
        w_args = deepcopy(FLOW_ARGS)
        w_args['workflows'].append((self.owner, self.suite_name, None))
        args = {}
        ids = [parse_node_id(n, TASK_PROXIES) for n in self.node_ids]
        response = _run_coroutine(
            self.resolvers.nodes_mutator(
                None, 'trigger_tasks', ids, w_args, args))
        self.assertEqual(response[0]['id'], self.workflow_id)

    def test_mutation_mapper(self):
        """Test the mapping of mutations to internal command methods."""
        response = _run_coroutine(
            self.resolvers._mutation_mapper('hold_suite', {}))
        self.assertIsNotNone(response)


if __name__ == '__main__':
    main()

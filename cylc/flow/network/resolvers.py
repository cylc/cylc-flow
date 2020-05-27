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

"""GraphQL resolvers for use in data accessing and mutation of workflows."""

from fnmatch import fnmatchcase
from getpass import getuser
from operator import attrgetter
from graphene.utils.str_converters import to_snake_case

from cylc.flow import ID_DELIM
from cylc.flow.data_store_mgr import (
    EDGES, FAMILY_PROXIES, TASK_PROXIES, WORKFLOW
)
from cylc.flow.network.schema import NodesEdges, PROXY_NODES


# Message Filters
def collate_workflow_atts(workflow):
    """Collate workflow filter attributes, setting defaults if non-existent."""
    # Append new atts to the end of the list,
    # this will retain order used in index access.
    return [
        workflow.owner,
        workflow.name,
        workflow.status,
    ]


def workflow_ids_filter(w_atts, items):
    """Match id arguments with workflow attributes.

    Returns a boolean."""
    # Return true if workflow matches any id arg.
    for owner, name, status in set(items):
        if ((not owner or fnmatchcase(w_atts[0], owner)) and
                (not name or fnmatchcase(w_atts[1], name)) and
                (not status or w_atts[2] == status)):
            return True
    return False


def workflow_filter(flow, args):
    """Filter workflows based on attribute arguments"""
    w_atts = collate_workflow_atts(flow[WORKFLOW])
    # The w_atts (workflow attributes) list contains ordered workflow values
    # or defaults (see collate function for index item).
    return ((not args.get('workflows') or
             workflow_ids_filter(w_atts, args['workflows'])) and
            not (args.get('exworkflows') and
                 workflow_ids_filter(w_atts, args['exworkflows'])))


def collate_node_atts(node):
    """Collate node filter attributes, setting defaults if non-existent."""
    owner, workflow, _ = node.id.split(ID_DELIM, 2)
    # Append new atts to the end of the list,
    # this will retain order used in index access
    # 0 - owner
    # 1 - workflow
    # 2 - Cycle point or None
    # 3 - name or namespace list
    # 4 - submit number or None
    # 5 - state
    return [
        owner,
        workflow,
        getattr(node, 'cycle_point', None),
        getattr(node, 'namespace', [node.name]),
        getattr(node, 'submit_num', None),
        getattr(node, 'state', None),
    ]


def node_ids_filter(n_atts, items):
    """Match id arguments with node attributes.

    Returns a boolean."""
    for owner, workflow, cycle, name, submit_num, state in items:
        if ((not owner or fnmatchcase(n_atts[0], owner)) and
                (not workflow or fnmatchcase(n_atts[1], workflow)) and
                (not cycle or fnmatchcase(n_atts[2], cycle)) and
                any(fnmatchcase(nn, name) for nn in n_atts[3]) and
                (not submit_num or
                 fnmatchcase(str(n_atts[4]), submit_num.lstrip('0'))) and
                (not state or n_atts[5] == state)):
            return True
    return False


def node_filter(node, args):
    """Filter nodes based on attribute arguments"""
    n_atts = collate_node_atts(node)
    # The n_atts (node attributes) list contains ordered node values
    # or defaults (see collate function for index item).
    return (
        (args.get('ghosts') or n_atts[5] != '') and
        (not args.get('states') or n_atts[5] in args['states']) and
        not (args.get('exstates') and n_atts[5] in args['exstates']) and
        (args.get('is_held') is None
         or (node.is_held == args['is_held'])) and
        (args.get('mindepth', -1) < 0 or node.depth >= args['mindepth']) and
        (args.get('maxdepth', -1) < 0 or node.depth <= args['maxdepth']) and
        # Now filter node against id arg lists
        (not args.get('ids') or node_ids_filter(n_atts, args['ids'])) and
        not (args.get('exids') and node_ids_filter(n_atts, args['exids']))
    )


def get_flow_data_from_ids(data_store, native_ids):
    """Return workflow data by id."""
    w_ids = set()
    for native_id in native_ids:
        o_name, w_name, _ = native_id.split(ID_DELIM, 2)
        flow_id = f'{o_name}{ID_DELIM}{w_name}'
        w_ids.add(flow_id)
    return [
        data_store[w_id]
        for w_id in w_ids
        if w_id in data_store
    ]


def get_data_elements(flow, nat_ids, element_type):
    """Return data elements by id."""
    return [
        flow[element_type][n_id]
        for n_id in nat_ids
        if n_id in flow[element_type]
    ]


def sort_elements(elements, args):
    """Sort iterable of elements by given attribute."""
    sort_args = args.get('sort')
    if sort_args and elements:
        sort_keys = [
            key
            for key in [to_snake_case(k) for k in sort_args.keys]
            if hasattr(elements[0], key)
        ]
        if sort_keys:
            elements.sort(
                key=attrgetter(*sort_keys),
                reverse=sort_args.reverse)
    return elements


class BaseResolvers:
    """Data access methods for resolving GraphQL queries."""

    def __init__(self, data):
        self.data = data

    # Query resolvers
    async def get_workflows_data(self, args):
        """Return list of data from workflows."""
        return [
            flow
            for flow in self.data.values()
            if workflow_filter(flow, args)]

    async def get_workflows(self, args):
        """Return workflow elements."""
        return sort_elements(
            [flow[WORKFLOW]
             for flow in await self.get_workflows_data(args)],
            args)

    # nodes
    async def get_nodes_all(self, node_type, args):
        """Return nodes from all workflows, filter by args."""
        return sort_elements(
            [n
             for flow in await self.get_workflows_data(args)
             for n in flow.get(node_type).values()
             if node_filter(n, args)],
            args)

    async def get_nodes_by_ids(self, node_type, args):
        """Return protobuf node objects for given id."""
        nat_ids = set(args.get('native_ids', []))
        if node_type == PROXY_NODES:
            node_types = [TASK_PROXIES, FAMILY_PROXIES]
        else:
            node_types = [node_type]
        return sort_elements(
            [node
             for flow in get_flow_data_from_ids(self.data, nat_ids)
             for node_type in node_types
             for node in get_data_elements(flow, nat_ids, node_type)
             if node_filter(node, args)],
            args)

    async def get_node_by_id(self, node_type, args):
        """Return protobuf node object for given id."""
        n_id = args.get('id')
        o_name, w_name, _ = n_id.split(ID_DELIM, 2)
        w_id = f'{o_name}{ID_DELIM}{w_name}'
        flow = self.data.get(w_id)
        if not flow:
            return None
        if node_type == PROXY_NODES:
            return (
                flow[TASK_PROXIES].get(n_id) or
                flow[FAMILY_PROXIES].get(n_id))
        return flow[node_type].get(n_id)

    # edges
    async def get_edges_all(self, args):
        """Return edges from all workflows, filter by args."""
        return sort_elements(
            [e
             for flow in await self.get_workflows_data(args)
             for e in flow.get(EDGES).values()],
            args)

    async def get_edges_by_ids(self, args):
        """Return protobuf edge objects for given id."""
        # TODO: Filter by given native ids.
        nat_ids = set(args.get('native_ids', []))
        return sort_elements(
            [edge
             for flow in get_flow_data_from_ids(self.data, nat_ids)
             for edge in get_data_elements(flow, nat_ids, EDGES)],
            args)

    async def get_nodes_edges(self, root_nodes, args):
        """Return nodes and edges within a specified distance of root nodes."""
        # Initial root node selection.
        nodes = root_nodes
        node_ids = set(n.id for n in root_nodes)
        edges = []
        edge_ids = set()
        # Setup for edgewise search.
        new_nodes = root_nodes
        for _ in range(args['distance']):
            # Gather edges.
            # Edges should be unique (graph not circular),
            # but duplicates will be present as node holds all associated.
            new_edge_ids = set(
                e_id
                for n in new_nodes
                for e_id in n.edges).difference(edge_ids)
            edge_ids.update(new_edge_ids)
            new_edges = [
                edge
                for flow in get_flow_data_from_ids(self.data, new_edge_ids)
                for edge in get_data_elements(flow, new_edge_ids, EDGES)
            ]
            edges += new_edges
            # Gather nodes.
            # One of source or target will be in current set of nodes.
            new_node_ids = set(
                [e.source for e in new_edges]
                + [e.target for e in new_edges]).difference(node_ids)
            # Stop searching on no new nodes
            if not new_node_ids:
                break
            node_ids.update(new_node_ids)
            new_nodes = [
                node
                for flow in get_flow_data_from_ids(self.data, new_node_ids)
                for node in get_data_elements(flow, new_node_ids, TASK_PROXIES)
            ]
            nodes += new_nodes

        return NodesEdges(
            nodes=sort_elements(nodes, args),
            edges=sort_elements(edges, args))


class Resolvers(BaseResolvers):
    """Workflow Service context GraphQL query and mutation resolvers."""

    schd = None

    def __init__(self, data, **kwargs):
        super().__init__(data)

        # Set extra attributes
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    # Mutations
    async def mutator(self, *m_args):
        """Mutate workflow."""
        _, command, w_args, args = m_args
        w_ids = [flow[WORKFLOW].id
                 for flow in await self.get_workflows_data(w_args)]
        if not w_ids:
            return 'Error: No matching Workflow'
        w_id = w_ids[0]
        result = await self._mutation_mapper(command, args)
        if result is None:
            result = (True, 'Command queued')
        return [{'id': w_id, 'response': result}]

    async def nodes_mutator(self, *m_args):
        """Mutate node items of associated workflows."""
        _, command, ids, w_args, args = m_args
        w_ids = [flow[WORKFLOW].id
                 for flow in await self.get_workflows_data(w_args)]
        if not w_ids:
            return 'Error: No matching Workflow'
        w_id = w_ids[0]
        # match proxy ID args with workflows
        items = []
        for owner, workflow, cycle, name, submit_num, state in ids:
            if workflow and owner is None:
                owner = "*"
            if (not (owner and workflow) or
                    fnmatchcase(w_id, f'{owner}{ID_DELIM}{workflow}')):
                if cycle is None:
                    cycle = '*'
                id_arg = f'{cycle}/{name}'
                if submit_num:
                    id_arg = f'{id_arg}/{submit_num}'
                if state:
                    id_arg = f'{id_arg}:{state}'
                items.append(id_arg)
        if items:
            if command == 'insert_tasks':
                args['items'] = items
            elif command == 'put_messages':
                args['task_job'] = items[0]
            else:
                args['task_globs'] = items
        result = await self._mutation_mapper(command, args)
        if result is None:
            result = (True, 'Command queued')
        return [{'id': w_id, 'response': result}]

    async def _mutation_mapper(self, command, kwargs):
        """Map between GraphQL resolvers and internal command interface."""
        method = getattr(self.schd.server, command)
        return method(user=getuser(), **kwargs)

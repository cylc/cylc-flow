# -*- coding: utf-8 -*-
# Copyright (C) 2019 NIWA & British Crown (Met Office) & Contributors.
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

from operator import attrgetter
from fnmatch import fnmatchcase

from cylc.flow.ws_data_mgr import ID_DELIM
from cylc.flow.network.schema import NodesEdges


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
    w_atts = collate_workflow_atts(flow['workflow'])
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


def sort_elements(elements, args):
    sort_args = args.get('sort')
    if sort_args and elements:
        sort_keys = [
            key
            for key in sort_args.keys
            if hasattr(elements[0], key)
        ]
        if sort_keys:
            elements.sort(
                key=attrgetter(*sort_keys),
                reverse=sort_args.reverse)
    return elements


class BaseResolvers(object):
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
            [flow['workflow']
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
        w_ids = set()
        for nat_id in nat_ids:
            o_name, w_name, _ = nat_id.split(ID_DELIM, 2)
            flow_id = f'{o_name}{ID_DELIM}{w_name}'
            if flow_id in self.data:
                w_ids.add(flow_id)
        if node_type == 'proxy_nodes':
            return sort_elements(
                [node
                 for flow in [self.data[w_id] for w_id in w_ids]
                 for node in (
                     [flow['task_proxies'][n_id]
                      for n_id in nat_ids
                      if n_id in flow['task_proxies']] +
                     [flow['family_proxies'][n_id]
                      for n_id in nat_ids
                      if n_id in flow['family_proxies']])
                 if node_filter(node, args)],
                args)
        return sort_elements(
            [node
             for flow in [self.data[w_id] for w_id in w_ids]
             for node in [flow[node_type][n_id]
                          for n_id in nat_ids
                          if n_id in flow[node_type]]
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
        if node_type == 'proxy_nodes':
            return (
                flow['task_proxies'].get(n_id) or
                flow['family_proxies'].get(n_id))
        return flow[node_type].get(n_id)

    # edges
    async def get_edges_all(self, args):
        """Return edges from all workflows, filter by args."""
        return sort_elements(
            [e
             for flow in await self.get_workflows_data(args)
             for e in flow.get('edges').values()],
            args)

    async def get_edges_by_ids(self, args):
        """Return protobuf edge objects for given id."""
        # TODO: Filter by given native ids.
        nat_ids = set(args.get('native_ids', []))
        w_ids = set()
        for nat_id in nat_ids:
            oname, wname, _ = nat_id.split(ID_DELIM, 2)
            w_ids.add(f'{oname}{ID_DELIM}{wname}')
        return sort_elements(
            [edge
             for flow in [self.data[w_id] for w_id in w_ids]
             for edge in [flow['edges'][e_id]
                          for e_id in nat_ids
                          if e_id in flow['edges']]],
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
            w_ids = set()
            for edge_id in new_edge_ids:
                o_name, w_name, _ = edge_id.split(ID_DELIM, 2)
                w_ids.add(f'{o_name}{ID_DELIM}{w_name}')
            new_edges = [
                edge
                for flow in [self.data[w_id] for w_id in w_ids]
                for edge in [
                    flow['edges'][e_id]
                    for e_id in new_edge_ids
                    if e_id in flow['edges']]
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
            w_ids = set()
            for node_id in new_node_ids:
                o_name, w_name, _ = node_id.split(ID_DELIM, 2)
                w_ids.add(f'{o_name}{ID_DELIM}{w_name}')
            new_nodes = [
                node
                for flow in [self.data[w_id] for w_id in w_ids]
                for node in [
                    flow['task_proxies'][n_id]
                    for n_id in new_node_ids
                    if n_id in flow['task_proxies']]
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
    async def mutator(self, info, command, w_args, args):
        """Mutate workflow."""
        w_ids = [flow['workflow'].id
                 for flow in await self.get_workflows_data(w_args)]
        if not w_ids:
            return 'Error: No matching Workflow'
        w_id = w_ids[0]
        result = await self._mutation_mapper(command, args)
        if result is None:
            result = (True, 'Command queued')
        return [{'id': w_id, 'response': result}]

    async def nodes_mutator(self, info, command, ids, w_args, args):
        """Mutate node items of associated workflows."""
        w_ids = [flow['workflow'].id
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

    async def _mutation_mapper(self, command, args):
        if command in ['clear_broadcast',
                       'expire_broadcast',
                       'put_broadcast']:
            return getattr(self.schd.task_events_mgr.broadcast_mgr,
                           command, None)(**args)
        elif command == 'put_ext_trigger':
            return self.schd.ext_trigger_queue.put((
                args.get('event_message'),
                args.get('event_id')))
        elif command == 'put_messages':
            messages = args.get('messages', [])
            for severity, message in messages:
                self.schd.message_queue.put((
                    args.get('task_job', None),
                    args.get('event_time', None),
                    severity, message))
            return (True, 'Messages queued: %d' % len(messages))
        elif command in ['set_stop_after_clock_time',
                         'set_stop_after_point',
                         'set_stop_after_task']:
            mutate_args = [command, (), {}]
            for val in args.values():
                mutate_args[1] = (val,)
            return self.schd.command_queue.put(tuple(mutate_args))
        else:
            mutate_args = [command, (), {}]
            for key, val in args.items():
                if isinstance(val, list):
                    mutate_args[1] = (val,)
                elif isinstance(val, dict):
                    mutate_args[2] = val
                else:
                    mutate_args[2][key] = val
            return self.schd.command_queue.put(tuple(mutate_args))

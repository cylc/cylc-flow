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
    w_atts = collate_workflow_atts(flow.workflow)
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
        (args.get('mindepth', -1) < 0 or node.depth >= args['mindepth']) and
        (args.get('maxdepth', -1) < 0 or node.depth <= args['maxdepth']) and
        # Now filter node against id arg lists
        (not args.get('ids') or node_ids_filter(n_atts, args['ids'])) and
        not (args.get('exids') and node_ids_filter(n_atts, args['exids']))
    )


def sort_elements(elements, args):
    sort_args = args.get('sort')
    if sort_args:
        elements.sort(
            key=attrgetter(*sort_args.keys),
            reverse=sort_args.reverse)
    return elements


class Resolvers(object):
    """Data access methods for resolving GraphQL queries in the workflow."""

    def __init__(self, schd):
        self.schd = schd

    # Query resolvers
    async def get_workflow_msgs(self, args):
        """Return list of workflows."""
        flow_msg = self.schd.ws_data_mgr.get_entire_workflow()
        if workflow_filter(flow_msg, args):
            return [flow_msg]
        return []

    # nodes
    async def get_nodes_all(self, node_type, args):
        """Return nodes from all workflows, filter by args."""
        return sort_elements(
            [n
             for k in await self.get_workflow_msgs(args)
             for n in getattr(k, node_type)
             if node_filter(n, args)],
            args)

    async def get_nodes_by_ids(self, node_type, args):
        """Return protobuf node objects for given id."""
        nat_ids = set(args.get('native_ids', []))
        w_ids = set()
        for nat_id in nat_ids:
            o_name, w_name, _ = nat_id.split(ID_DELIM, 2)
            w_ids.add(f'{o_name}{ID_DELIM}{w_name}')
        if self.schd.ws_data_mgr.workflow.id not in w_ids:
            return []
        flow_msg = self.schd.ws_data_mgr.get_entire_workflow()
        if node_type == 'proxy_nodes':
            nodes = (list(getattr(flow_msg, 'task_proxies', []))
                     + list(getattr(flow_msg, 'family_proxies', [])))
        else:
            nodes = list(getattr(flow_msg, node_type, []))
        return sort_elements(
            [node
             for node in nodes
             if node.id in nat_ids and node_filter(node, args)],
            args)

    async def get_node_by_id(self, node_type, args):
        """Return protobuf node object for given id."""
        n_id = args.get('id')
        o_name, w_name, _ = n_id.split(ID_DELIM, 2)
        w_id = f'{o_name}{ID_DELIM}{w_name}'
        if self.schd.ws_data_mgr.workflow.id != w_id:
            return None
        flow_msg = self.schd.ws_data_mgr.get_entire_workflow()
        if node_type == 'proxy_nodes':
            nodes = (
                list(getattr(flow_msg, 'task_proxies', []))
                + list(getattr(flow_msg, 'family_proxies', [])))
        else:
            nodes = getattr(flow_msg, node_type, [])
        for node in nodes:
            if node.id == n_id:
                return node
        return None

    # edges
    async def get_edges_all(self, args):
        """Return edges from all workflows, filter by args."""
        return sort_elements(
            [e
             for w in await self.get_workflow_msgs(args)
             for e in getattr(w, 'edges')],
            args)

    async def get_edges_by_ids(self, args):
        """Return protobuf edge objects for given id."""
        # TODO: Filter by given native ids.
        nat_ids = set(args.get('native_ids', []))
        w_ids = set()
        for nat_id in nat_ids:
            oname, wname, _ = nat_id.split(ID_DELIM, 2)
            w_ids.add(f'{oname}{ID_DELIM}{wname}')
        if self.schd.ws_data_mgr.workflow.id not in w_ids:
            return []
        edges = getattr(self.schd.ws_data_mgr.get_entire_workflow(), 'edges')
        return sort_elements(
            [edge
             for edge in edges
             if edge.id in nat_ids],
            args)

    # Mutations
    async def mutator(self, info, command, w_args, args):
        """Mutate workflow."""
        w_ids = [flow.workflow.id
                 for flow in await self.get_workflow_msgs(w_args)]
        if not w_ids:
            return 'Error: No matching Workflow'
        w_id = w_ids[0]
        result = await self._mutation_mapper(command, args)
        if result is None:
            result = (True, 'Command queued')
        return [{'id': w_id, 'response': result}]

    async def nodes_mutator(self, info, command, ids, w_args, args):
        """Mutate node items of associated workflows."""
        w_ids = [flow.workflow.id
                 for flow in await self.get_workflow_msgs(w_args)]
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

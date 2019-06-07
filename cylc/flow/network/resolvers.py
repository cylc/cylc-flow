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

from fnmatch import fnmatchcase


class Resolvers(object):

    def __init__(self, schd):
        self.schd = schd

    # Query resolvers
    # workflows
    async def get_workflow_msgs(self, args):
        """Return list of workflows."""
        result = []
        flow_msg = self.schd.ws_data_mgr.get_entire_workflow()
        if self._workflow_filter(flow_msg, args):
            result.append(flow_msg)
        # TODO: Sorting and Pagination
        return result

    def _workflow_filter(self, flow, args):
        """Filter workflows based on attribute arguments"""
        natts = self._collate_workflow_atts(flow.workflow)
        return ((not args.get('workflows') or
                self._workflow_atts_filter(natts, args['workflows'])) and
                not (args.get('exworkflows') and
                     self._workflow_atts_filter(natts, args['exworkflows'])))

    # nodes
    async def get_nodes_all(self, node_type, args):
        """Return nodes from all workflows, filter by args."""
        nodes = [
            n for k in await self.get_workflow_msgs(args)
            for n in getattr(k, node_type)]
        result = []
        for node in nodes:
            if self._node_filter(node, args):
                result.append(node)
        # TODO: Sorting and Pagination
        return result

    async def get_nodes_by_id(self, node_type, args):
        """Return protobuf node objects for given id."""
        nat_ids = args.get('native_ids', [])
        w_ids = []
        for nat_id in nat_ids:
            o_name, w_name, _ = nat_id.split('/', 2)
            w_ids.append(f'{o_name}/{w_name}')
        if self.schd.ws_data_mgr.workflow.id not in set(w_ids):
            return []
        flow_msg = self.schd.ws_data_mgr.get_entire_workflow()
        if node_type == 'proxy_nodes':
            nodes = list(list(getattr(flow_msg, 'task_proxies', []))
                         + list(getattr(flow_msg, 'family_proxies', [])))
        else:
            nodes = list(getattr(flow_msg, node_type, []))
        result = []
        for node in nodes:
            if ((not nat_ids or node.id in set(nat_ids)) and
                    self._node_filter(node, args)):
                result.append(node)
        # TODO: Sorting and Pagination
        return result

    def _node_filter(self, node, args):
        """Filter nodes based on attribute arguments"""
        natts = self._collate_node_atts(node)
        return ((not args.get('states') or node.state in args['states']) and
                not (args.get('exstates') and
                     node.state in args['exstates']) and
                (args.get('mindepth', -1) < 0 or
                    node.depth >= args['mindepth']) and
                (args.get('maxdepth', -1) < 0 or
                    node.depth <= args['maxdepth']) and
                (not args.get('ids') or
                    self._node_atts_filter(natts, args['ids'])) and
                not (args.get('exids') and
                     self._node_atts_filter(natts, args['exids'])))

    async def get_node_by_id(self, node_type, args):
        """Return protobuf node object for given id."""
        n_id = args.get('id')
        o_name, w_name, _ = n_id.split('/', 2)
        w_id = f'{o_name}/{w_name}'
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
        result = []
        for edge in [
                n for k in await self.get_workflow_msgs(args)
                for n in getattr(k, 'edges')]:
            result.append(edge)
        # TODO: Sorting and Pagination
        return result

    async def get_edges_by_id(self, args):
        """Return protobuf edge objects for given id."""
        nat_ids = args.get('native_ids', [])
        w_ids = []
        for nat_id in nat_ids:
            oname, wname, _ = nat_id.split('/', 2)
            w_ids.append(f'{oname}/{wname}')
        if self.schd.ws_data_mgr.workflow.id not in set(w_ids):
            return []
        flow_msg = self.schd.ws_data_mgr.get_entire_workflow()
        result = []
        for edge in list(getattr(flow_msg, 'edges')):
            result.append(edge)
        # TODO: Sorting and Pagination
        return result

    # Mutations
    async def mutator(self, command, w_args, args):
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

    async def nodes_mutator(self, command, ids, w_args, args):
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
                    fnmatchcase(w_id, f'{owner}/{workflow}')):
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

    # Message Filters
    @staticmethod
    def _collate_workflow_atts(workflow):
        """Collate workflow filter attributes."""
        return [
            workflow.owner,
            workflow.name,
            workflow.status,
        ]

    @staticmethod
    def _workflow_atts_filter(natts, items):
        """Match components of id argument with those of workflow id."""
        for owner, name, status in set(items):
            if ((not owner or fnmatchcase(natts[0], owner)) and
                    (not name or fnmatchcase(natts[1], name)) and
                    (not status or natts[2] == status)):
                return True
        return False

    @staticmethod
    def _collate_node_atts(node):
        """Collate node filter attributes."""
        node_id = getattr(node, 'id')
        slash_count = node_id.count('/')
        n_id = node_id.split('/', slash_count)
        if slash_count == 2:
            n_cycle = None
            n_name = n_id[2]
        else:
            n_cycle = n_id[2]
            n_name = n_id[3]
        return [
            n_id[0],
            n_id[1],
            n_cycle,
            getattr(node, 'namespace', [n_name]),
            getattr(node, 'submit_num', None),
            getattr(node, 'state', None),
        ]

    @staticmethod
    def _node_atts_filter(natts, items):
        """Match node id argument with node attributes."""
        for owner, workflow, cycle, name, submit_num, state in items:
            if ((not owner or fnmatchcase(natts[0], owner)) and
                    (not workflow or fnmatchcase(natts[1], workflow)) and
                    (not cycle or fnmatchcase(natts[2], cycle)) and
                    any(fnmatchcase(nn, name) for nn in natts[3]) and
                    (not submit_num or
                        fnmatchcase(str(natts[4]), submit_num.lstrip('0'))) and
                    (not state or natts[5] == state)):
                return True
        return False

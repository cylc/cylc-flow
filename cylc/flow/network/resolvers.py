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

import asyncio
from fnmatch import fnmatchcase
import logging
from operator import attrgetter
import queue
from time import time
from uuid import uuid4

from graphene.utils.str_converters import to_snake_case

from cylc.flow import ID_DELIM
from cylc.flow.data_store_mgr import (
    EDGES, FAMILY_PROXIES, TASK_PROXIES, WORKFLOW,
    DELTA_ADDED, create_delta_store
)
from cylc.flow.network.schema import (
    NodesEdges, PROXY_NODES, SUB_RESOLVERS, parse_node_id
)

logger = logging.getLogger(__name__)

DELTA_SLEEP_INTERVAL = 0.5


def filter_none(dictionary):
    """Filter out `None` items from a dictionary:

    Examples:
        >>> filter_none({
        ...     'a': 0,
        ...     'b': '',
        ...     'c': None
        ... })
        {'a': 0, 'b': ''}

    """
    return {
        key: value
        for key, value in dictionary.items()
        if value is not None
    }


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


def workflow_filter(flow, args, w_atts=None):
    """Filter workflows based on attribute arguments"""
    if w_atts is None:
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


def node_filter(node, node_type, args):
    """Filter nodes based on attribute arguments"""
    # Updated delta nodes don't contain name but still need filter
    if not node.name:
        n_atts = list(parse_node_id(node.id, node_type))
        n_atts[3] = [n_atts[3]]
    else:
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

    def __init__(self, data_store_mgr):
        self.data_store_mgr = data_store_mgr
        self.delta_store = {}

    # Query resolvers
    async def get_workflow_by_id(self, args):
        """Return a workflow store by ID."""
        try:
            if 'sub_id' in args and args['delta_store']:
                return self.delta_store[args['sub_id']][args['id']][
                    args['delta_type']][WORKFLOW]
            return self.data_store_mgr.data[args['id']][WORKFLOW]
        except KeyError:
            return None

    async def get_workflows_data(self, args):
        """Return list of data from workflows."""
        # Both cases just as common so 'if' not 'try'
        if 'sub_id' in args and args['delta_store']:
            return [
                delta[args['delta_type']]
                for key, delta in self.delta_store[args['sub_id']].items()
                if workflow_filter(self.data_store_mgr.data[key], args)
            ]
        return [
            flow
            for flow in self.data_store_mgr.data.values()
            if workflow_filter(flow, args)
        ]

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
             if node_filter(n, node_type, args)],
            args)

    async def get_nodes_by_ids(self, node_type, args):
        """Return protobuf node objects for given id."""
        nat_ids = set(args.get('native_ids', []))
        # Both cases just as common so 'if' not 'try'
        if 'sub_id' in args and args['delta_store']:
            flow_data = [
                delta[args['delta_type']]
                for delta in get_flow_data_from_ids(
                    self.delta_store[args['sub_id']], nat_ids)
            ]
        else:
            flow_data = get_flow_data_from_ids(
                self.data_store_mgr.data, nat_ids)

        if node_type == PROXY_NODES:
            node_types = [TASK_PROXIES, FAMILY_PROXIES]
        else:
            node_types = [node_type]
        return sort_elements(
            [node
             for flow in flow_data
             for node_type in node_types
             for node in get_data_elements(flow, nat_ids, node_type)
             if node_filter(node, node_type, args)],
            args)

    async def get_node_by_id(self, node_type, args):
        """Return protobuf node object for given id."""
        n_id = args.get('id')
        o_name, w_name, _ = n_id.split(ID_DELIM, 2)
        w_id = f'{o_name}{ID_DELIM}{w_name}'
        # Both cases just as common so 'if' not 'try'
        try:
            if 'sub_id' in args and args.get('delta_store'):
                flow = self.delta_store[
                    args['sub_id']][w_id][args['delta_type']]
            else:
                flow = self.data_store_mgr.data[w_id]
        except KeyError:
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
        nat_ids = set(args.get('native_ids', []))
        if 'sub_id' in args and args['delta_store']:
            flow_data = [
                delta[args['delta_type']]
                for delta in get_flow_data_from_ids(
                    self.delta_store[args['sub_id']], nat_ids)
            ]
        else:
            flow_data = get_flow_data_from_ids(
                self.data_store_mgr.data, nat_ids)

        return sort_elements(
            [edge
             for flow in flow_data
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
                for flow in get_flow_data_from_ids(
                    self.data_store_mgr.data, new_edge_ids)
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
                for flow in get_flow_data_from_ids(
                    self.data_store_mgr.data, new_node_ids)
                for node in get_data_elements(flow, new_node_ids, TASK_PROXIES)
            ]
            nodes += new_nodes

        return NodesEdges(
            nodes=sort_elements(nodes, args),
            edges=sort_elements(edges, args))

    async def subscribe_delta(self, root, info, args):
        """Delta subscription async generator.

        Async generator mapping the incomming protobuf deltas to
        yielded GraphQL subscription objects.

        """
        workflow_ids = set(args.get('workflows', args.get('ids', ())))
        sub_id = uuid4()
        info.context['sub_id'] = sub_id
        self.delta_store[sub_id] = {}
        delta_queues = self.data_store_mgr.delta_queues
        deltas_queue = queue.Queue()
        try:
            # Iterate over the queue yielding deltas
            w_ids = workflow_ids
            sub_resolver = SUB_RESOLVERS.get(to_snake_case(info.field_name))
            interval = args['ignore_interval']
            old_time = time()
            while True:
                if not workflow_ids:
                    old_ids = w_ids
                    w_ids = set(delta_queues.keys())
                    for remove_id in old_ids.difference(w_ids):
                        if remove_id in self.delta_store[sub_id]:
                            del self.delta_store[sub_id][remove_id]
                            if sub_resolver is None:
                                yield create_delta_store(workflow_id=remove_id)
                            else:
                                yield await sub_resolver(root, info, **args)
                for w_id in w_ids:
                    if w_id in self.data_store_mgr.data:
                        if sub_id not in delta_queues[w_id]:
                            delta_queues[w_id][sub_id] = deltas_queue
                            # On new yield workflow data-store as added delta
                            if args.get('initial_burst'):
                                delta_store = create_delta_store(
                                    workflow_id=w_id)
                                delta_store[DELTA_ADDED] = (
                                    self.data_store_mgr.data[w_id])
                                self.delta_store[sub_id][w_id] = delta_store
                                if sub_resolver is None:
                                    yield delta_store
                                else:
                                    result = await sub_resolver(
                                        root, info, **args)
                                    if result:
                                        yield result
                    elif w_id in self.delta_store[sub_id]:
                        del self.delta_store[sub_id][w_id]
                try:
                    w_id, topic, delta_store = deltas_queue.get(False)
                    if topic != 'shutdown':
                        new_time = time()
                        elapsed = new_time - old_time
                        # ignore deltas that are more frequent than interval.
                        if elapsed <= interval:
                            continue
                        old_time = new_time
                    else:
                        delta_store['shutdown'] = True
                    self.delta_store[sub_id][w_id] = delta_store
                    if sub_resolver is None:
                        yield delta_store
                    else:
                        result = await sub_resolver(root, info, **args)
                        if result:
                            yield result
                except queue.Empty:
                    await asyncio.sleep(DELTA_SLEEP_INTERVAL)
        except (GeneratorExit, asyncio.CancelledError):
            raise
        except Exception:
            import traceback
            logger.warning(traceback.format_exc())
        finally:
            for w_id in w_ids:
                if delta_queues.get(w_id, {}).get(sub_id):
                    del delta_queues[w_id][sub_id]
            if sub_id in self.delta_store:
                del self.delta_store[sub_id]
            yield None


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
            if command == 'put_messages':
                args['task_job'] = items[0]
            else:
                args['task_globs'] = items
        result = await self._mutation_mapper(command, args)
        if result is None:
            result = (True, 'Command queued')
        return [{'id': w_id, 'response': result}]

    async def _mutation_mapper(self, command, kwargs):
        """Map between GraphQL resolvers and internal command interface."""
        method = getattr(self, command)
        return method(**kwargs)

    def broadcast(
            self,
            mode,
            cycle_points=None,
            namespaces=None,
            settings=None,
            cutoff=None
    ):
        """Put or clear broadcasts."""
        if mode == 'put_broadcast':
            return self.schd.task_events_mgr.broadcast_mgr.put_broadcast(
                cycle_points, namespaces, settings)
        if mode == 'clear_broadcast':
            return self.schd.task_events_mgr.broadcast_mgr.clear_broadcast(
                cycle_points, namespaces, settings)
        if mode == 'expire_broadcast':
            return self.schd.task_events_mgr.broadcast_mgr.expire_broadcast(
                cutoff)
        raise ValueError('Unsupported broadcast mode')

    def hold(self, tasks=None, time=None):
        """Hold the workflow."""
        self.schd.command_queue.put((
            'hold',
            tuple(),
            filter_none({
                'tasks': tasks or None,
                'time': time
            })
        ))
        return (True, 'Command queued')

    def kill_tasks(self, tasks):
        """Kill task jobs.

        Args:
            tasks (list): List of identifiers, see `task globs`_

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("kill_tasks", (tasks,), {}))
        return (True, 'Command queued')

    def remove_tasks(self, tasks):
        """Remove tasks from the task pool.

        Args:
            tasks (list):
                List of identifiers, see `task globs`

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("remove_tasks", (tasks,), {}))
        return (True, 'Command queued')

    def poll_tasks(self, tasks=None):
        """Request the suite to poll task jobs.

        Args:
            tasks (list, optional):
                List of identifiers, see `task globs`_
        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("poll_tasks", (tasks,), {}))
        return (True, 'Command queued')

    def put_ext_trigger(self, message, id):
        """Server-side external event trigger interface.

        Args:
            message (str): The external trigger message.
            id (str): The unique trigger ID.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.ext_trigger_queue.put((message, id))
        return (True, 'Event queued')

    def put_messages(self, task_job=None, event_time=None, messages=None):
        """Put task messages in queue for processing later by the main loop.

        Arguments:
            task_job (str, optional):
                Task job in the format ``CYCLE/TASK_NAME/SUBMIT_NUM``.
            event_time (str, optional):
                Event time as an ISO8601 string.
            messages (list, optional):
                List in the format ``[[severity, message], ...]``.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        #  TODO: standardise the task_job interface to one of the other
        #        systems
        for severity, message in messages:
            self.schd.message_queue.put(
                (task_job, event_time, severity, message))
        return (True, 'Messages queued: %d' % len(messages))

    def reload_suite(self):
        """Tell suite to reload the suite definition.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("reload_suite", (), {}))
        return (True, 'Command queued')

    def release(self, tasks=None):
        """Release (un-hold) the workflow."""
        self.schd.command_queue.put((
            "release",
            (),
            filter_none({
                'ids': tasks
            })
        ))
        return (True, 'Command queued')

    def set_verbosity(self, level):
        """Set suite verbosity to new level (for suite logs).

        Args:
            level (str): A logging level e.g. ``INFO`` or ``ERROR``.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(("set_verbosity", (level,), {}))
        return (True, 'Command queued')

    def set_graph_window_extent(self, n_edge_distance):
        """Set data-store graph window to new max edge distance.

        Args:
            n_edge_distance (int):
                Max edge distance 0..n from active node.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        if n_edge_distance >= 0:
            self.schd.data_store_mgr.set_graph_window_extent(n_edge_distance)
            return (True, f'Maximum edge distance set to {n_edge_distance}')
        else:
            return (False, 'Edge distance cannot be negative')

    def force_spawn_children(self, tasks, outputs):
        """Spawn children of given task outputs.

        Args:
            tasks (list): List of identifiers, see `task globs`
            outputs (list): List of outputs to spawn on

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("force_spawn_children", (tasks,),
             {'outputs': outputs}))
        return (True, 'Command queued')

    def stop(
            self,
            mode=None,
            cycle_point=None,
            clock_time=None,
            task=None,
            flow_label=None
    ):
        """Stop the workflow or specific flow from spawning any further.

        Args:
            mode (StopMode.Value): Stop mode to set
            cycle_point (str): Cycle point after which to stop.
            clock_time (str): Wallclock time after which to stop.
            task (str): Stop after this task succeeds.
            flow_label (str): The flow to sterilise.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put((
            "stop",
            (),
            filter_none({
                'mode': mode,
                'cycle_point': cycle_point,
                'clock_time': clock_time,
                'task': task,
                'flow_label': flow_label,
            })
        ))
        return (True, 'Command queued')

    def force_trigger_tasks(self, tasks, reflow=False):
        """Trigger submission of task jobs where possible.

        Args:
            tasks (list):
                List of identifiers, see `task globs`_
            reflow (bool, optional):
                Start new flow(s) from triggered tasks.

        Returns:
            tuple: (outcome, message)

            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            ("force_trigger_tasks", (tasks,),
             {"reflow": reflow}))
        return (True, 'Command queued')

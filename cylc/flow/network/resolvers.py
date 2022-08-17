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

"""GraphQL resolvers for use in data accessing and mutation of workflows."""

from abc import ABCMeta, abstractmethod
import asyncio
from contextlib import suppress
from fnmatch import fnmatchcase
import logging
import queue
from time import time
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    TYPE_CHECKING,
    Union,
)
from uuid import uuid4

from graphene.utils.str_converters import to_snake_case
from cylc.flow import LOG

from cylc.flow.data_store_mgr import (
    EDGES, FAMILY_PROXIES, TASK_PROXIES, WORKFLOW,
    DELTA_ADDED, create_delta_store
)
from cylc.flow.id import Tokens
from cylc.flow.network.schema import (
    DEF_TYPES,
    NodesEdges,
    PROXY_NODES,
    SUB_RESOLVERS,
    sort_elements,
)

if TYPE_CHECKING:
    from uuid import UUID
    from graphql import ResolveInfo
    from cylc.flow.data_store_mgr import DataStoreMgr
    from cylc.flow.scheduler import Scheduler
    from cylc.flow.workflow_status import StopMode


logger = logging.getLogger(__name__)

DELTA_SLEEP_INTERVAL = 0.5
# Delay before carrying on with the next delta,
# roughly DELTA_PROC_WAIT*DELTA_SLEEP_INTERVAL seconds (if queue is empty).
DELTA_PROC_WAIT = 10


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
    return {
        'user': workflow.owner,
        'workflow': workflow.name,
        'workflow_sel': workflow.status,
    }


def uniq(iterable):
    """Return a unique collection of the provided items preserving item order.

    Useful for unhashable things like dicts, relies on __eq__ for testing
    equality.

    Examples:
        >>> uniq([1, 1, 2, 3, 5, 8, 1])
        [1, 2, 3, 5, 8]

    """
    ret = []
    for item in iterable:
        if item not in ret:
            ret.append(item)
    return ret


def workflow_ids_filter(workflow_tokens, items) -> bool:
    """Match id arguments with workflow attributes.

    Return True if workflow matches any id arg.
    """
    return any(
        (
            (
                not item['user']
                or fnmatchcase(workflow_tokens['user'], item['user'])
            )
            and (
                not item['workflow']
                or fnmatchcase(workflow_tokens['workflow'], item['workflow'])
            )
            and (
                not item['workflow_sel']
                or workflow_tokens['workflow_sel'] == item['workflow_sel']
            )
        )
        for item in uniq(items)
    )


def workflow_filter(flow, args, w_atts=None) -> bool:
    """Filter workflows based on attribute arguments"""
    if w_atts is None:
        w_atts = collate_workflow_atts(flow[WORKFLOW])
    # The w_atts (workflow attributes) list contains ordered workflow values
    # or defaults (see collate function for index item).
    return (
        (
            not args.get('workflows')
            or workflow_ids_filter(w_atts, args['workflows'])
        )
        and not (
            args.get('exworkflows')
            and workflow_ids_filter(w_atts, args['exworkflows'])
        )
    )


def get_state_from_selectors(tokens):
    """Return the highest defined selector in the provided tokens or None.

    TODO:
        This is a temporary workaround, the filters here should acquire
        full selector capability in due course.

    """
    for selector in 'cycle_sel', 'task_sel', 'job_sel':
        if tokens.get(selector):
            return tokens[selector]


def node_ids_filter(tokens, state, items) -> bool:
    """Match id arguments with node attributes."""
    return any(
        (
            # don't match an empty string (globs should be implicit)
            not item.is_null
            # match cycle point
            and (
                not item['cycle']
                or fnmatchcase(tokens['cycle'], item['cycle'])
            )
            # match namespace name
            and (
                not item['task']
                or fnmatchcase(tokens['task'], item['task'])
            )
            # match job
            and (
                not item['job']
                or fnmatchcase(tokens['job'], item['job'])
            )
            # match cycle/task/job state
            and (
                not (
                    state is not None
                    and get_state_from_selectors(item)
                )
                or get_state_from_selectors(item) == state
            )
        )
        for item in uniq(items)
    )


def node_filter(node, node_type, args, state):
    """Filter nodes based on attribute arguments.

    Args:
        node: The node to filter (from the data or delta store).
        node_type: The type of the node being filtered.
        args: The query arguments.
        state: The state of the node that is being filtered.
            Note: can be None for non-tasks e.g. task definitions where
            state filtering does not apply.

    """
    tokens: Tokens
    if node_type in DEF_TYPES:
        # namespace nodes don't fit into the universal ID scheme so must
        # be tokenised manually
        tokens = Tokens(
            cycle=None,
            task=node.name,
            job=None,
        )
    else:
        # live objects can be represented by a universal ID
        tokens = Tokens(node.id)
    return (
        (
            (
                state is None
                or not args.get('states')
            )
            or state in args['states']
        )
        and (
            not args.get('exstates')
            or state not in args['exstates']
        )
        and (
            args.get('is_held') is None
            or (node.is_held == args['is_held'])
        )
        and (
            args.get('is_queued') is None
            or (node.is_queued == args['is_queued'])
        )
        and (
            args.get('mindepth', -1) < 0
            or node.depth >= args['mindepth']
        )
        and (
            args.get('maxdepth', -1) < 0
            or node.depth <= args['maxdepth']
        )
        # Now filter node against id arg lists
        and (
            not args.get('ids')
            or node_ids_filter(tokens, state, args['ids'])
        )
        and (
            not args.get('exids')
            or not node_ids_filter(tokens, state, args['exids'])
        )
    )


def get_flow_data_from_ids(data_store, native_ids):
    """Return workflow data by id."""
    w_ids = []
    for native_id in native_ids:
        w_ids.append(
            Tokens(native_id).workflow_id
        )
    return [
        data_store[w_id]
        for w_id in uniq(w_ids)
        if w_id in data_store
    ]


def get_data_elements(flow, nat_ids, element_type):
    """Return data elements by id."""
    flow_element = flow[element_type]
    return [
        flow_element[n_id]
        for n_id in nat_ids
        if n_id in flow_element
    ]


class BaseResolvers(metaclass=ABCMeta):  # noqa: SIM119
    """Data access methods for resolving GraphQL queries."""

    def __init__(self, data_store_mgr: 'DataStoreMgr'):
        self.data_store_mgr = data_store_mgr
        # Used with subscriptions for a temporary delta-store,
        # [sub_id][w_id] = store
        self.delta_store: Dict['UUID', Dict[str, dict]] = {}
        # Used to serialised deltas from a single workflow, needed for
        # the management of a common data object.
        self.delta_processing_flows: Dict['UUID', set] = {}

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

    async def get_workflows_data(self, args: Dict[str, Any]):
        """Return list of data from workflows."""
        # Both cases just as common so 'if' not 'try'
        if 'sub_id' in args and args['delta_store']:
            return [
                delta[args['delta_type']]
                for key, delta in self.delta_store[args['sub_id']].items()
                if workflow_filter(self.data_store_mgr.data[key], args)
            ]
        return [
            workflow
            for workflow in self.data_store_mgr.data.values()
            if workflow_filter(workflow, args)
        ]

    async def get_workflows(self, args):
        """Return workflow elements."""
        return sort_elements(
            [flow[WORKFLOW]
             for flow in await self.get_workflows_data(args)],
            args)

    # nodes
    def get_node_state(self, node, node_type):
        """Return state, from node or data-store."""
        if node_type in DEF_TYPES:
            return None
        # NOTE: dont access "state" directly as the attribute might not exist
        with suppress(Exception):
            return (
                # try to retrieve the state from the node
                # (could be a delta-store node which might not have a state)
                getattr(node, 'state', None)
                # fall back to the data store (because this could be a
                # delta-store node which might not have the state field set)
                or self.data_store_mgr.data[
                    Tokens(node.id).workflow_id
                ][node_type][node.id].state
            )

    async def get_nodes_all(self, node_type, args):
        """Return nodes from all workflows, filter by args."""
        return sort_elements(
            [
                node
                for flow in await self.get_workflows_data(args)
                for node in flow.get(node_type).values()
                if node_filter(
                    node,
                    node_type,
                    args,
                    self.get_node_state(node, node_type)
                )
            ],
            args,
        )

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
            [
                node
                for flow in flow_data
                for node_type in node_types
                for node in get_data_elements(flow, nat_ids, node_type)
                if node_filter(
                    node,
                    node_type,
                    args,
                    self.get_node_state(node, node_type)
                )
            ],
            args,
        )

    async def get_node_by_id(self, node_type, args):
        """Return protobuf node object for given id."""
        n_id = args.get('id')
        w_id = Tokens(n_id).workflow_id
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
        node_ids = {n.id for n in root_nodes}
        edges = []
        edge_ids = set()
        # Setup for edgewise search.
        new_nodes = root_nodes
        for _ in range(args['distance']):
            # Gather edges.
            # Edges should be unique (graph not circular),
            # but duplicates will be present as node holds all associated.
            new_edge_ids = {
                e_id
                for n in new_nodes
                for e_id in n.edges
            }.difference(edge_ids)
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

        Async generator mapping the incoming protobuf deltas to
        yielded GraphQL subscription objects.

        """
        workflow_ids = set(args.get('workflows', args.get('ids', ())))
        sub_id = uuid4()
        info.variable_values['backend_sub_id'] = sub_id
        self.delta_store[sub_id] = {}

        op_id = root
        if 'ops_queue' not in info.context:
            info.context['ops_queue'] = {}
        info.context['ops_queue'][op_id] = queue.Queue()
        op_queue = info.context['ops_queue'][op_id]
        self.delta_processing_flows[sub_id] = set()
        delta_processing_flows = self.delta_processing_flows[sub_id]

        delta_queues = self.data_store_mgr.delta_queues
        deltas_queue = queue.Queue()

        counters = {}
        delta_yield_queue = queue.Queue()
        flow_delta_queues = {}
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
                                deltas_queue.put(
                                    (w_id, 'initial_burst', delta_store))
                    elif w_id in self.delta_store[sub_id]:
                        del self.delta_store[sub_id][w_id]
                try:
                    with suppress(queue.Empty):
                        w_id, topic, delta_store = deltas_queue.get(False)

                        if w_id not in flow_delta_queues:
                            counters[w_id] = 0
                            flow_delta_queues[w_id] = queue.Queue()
                        flow_delta_queues[w_id].put((topic, delta_store))

                    # Only yield deltas from the same workflow if previous
                    # delta has finished processing.
                    for flow_id, flow_queue in flow_delta_queues.items():
                        if flow_queue.empty():
                            continue
                        elif flow_id in delta_processing_flows:
                            if counters[flow_id] < DELTA_PROC_WAIT:
                                continue
                            delta_processing_flows.remove(flow_id)
                        counters[flow_id] = 0
                        topic, delta_store = flow_queue.get()
                        delta_yield_queue.put((flow_id, topic, delta_store))

                    w_id, topic, delta_store = delta_yield_queue.get(False)

                    # Handle shutdown delta, don't ignore.
                    if topic == 'shutdown':
                        delta_store['shutdown'] = True
                    else:
                        # ignore deltas that are more frequent than interval.
                        new_time = time()
                        elapsed = new_time - old_time
                        if elapsed <= interval:
                            continue
                        old_time = new_time

                    delta_processing_flows.add(w_id)
                    op_queue.put((sub_id, w_id))
                    self.delta_store[sub_id][w_id] = delta_store
                    if sub_resolver is None:
                        yield delta_store
                    else:
                        result = await sub_resolver(root, info, **args)
                        if result:
                            yield result
                except queue.Empty:
                    await asyncio.sleep(DELTA_SLEEP_INTERVAL)
                    for flow_id in delta_processing_flows:
                        counters[flow_id] += 1
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

    async def flow_delta_processed(self, context, op_id):
        if 'ops_queue' in context:
            with suppress(queue.Empty, KeyError):
                sub_id, w_id = context['ops_queue'][op_id].get(False)
                self.delta_processing_flows[sub_id].remove(w_id)

    @abstractmethod
    async def mutator(
        self,
        info: 'ResolveInfo',
        command: str,
        w_args: Dict[str, Any],
        kwargs: Dict[str, Any],
        meta: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        ...


class Resolvers(BaseResolvers):
    """Workflow Service context GraphQL query and mutation resolvers."""

    schd: 'Scheduler'

    def __init__(self, data: 'DataStoreMgr', schd: 'Scheduler') -> None:
        super().__init__(data)
        self.schd = schd

    # Mutations
    async def mutator(
        self,
        _info: 'ResolveInfo',
        command: str,
        w_args: Dict[str, Any],
        kwargs: Dict[str, Any],
        meta: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Mutate workflow."""
        w_ids = [flow[WORKFLOW].id
                 for flow in await self.get_workflows_data(w_args)]
        if not w_ids:
            workflows = list(self.data_store_mgr.data.keys())
            return [{
                'response': (False, f'No matching workflow in {workflows}')}]
        w_id = w_ids[0]
        result = await self._mutation_mapper(command, kwargs, meta)
        if result is None:
            result = (True, 'Command queued')
        return [{'id': w_id, 'response': result}]

    async def _mutation_mapper(
        self, command: str, kwargs: Dict[str, Any], meta: Dict[str, Any]
    ) -> Optional[Tuple[bool, str]]:
        """Map between GraphQL resolvers and internal command interface."""
        method = getattr(self, command, None)
        if method is not None:
            return method(**kwargs)
        try:
            self.schd.get_command_method(command)
        except AttributeError:
            raise ValueError(f"Command '{command}' not found")
        if command != "put_messages":
            log_msg = f"[command] {command}"
            user = meta.get('auth_user', self.schd.owner)
            if user != self.schd.owner:
                log_msg += (f" (issued by {user})")
            LOG.info(log_msg)
        self.schd.queue_command(
            command,
            kwargs
        )
        return None

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

    def put_ext_trigger(
        self,
        message,
        id  # noqa: A002 (graphql interface)
    ):
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

    def put_messages(
        self,
        task_job=None,
        event_time=None,
        messages=None
    ):
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

    def force_spawn_children(
        self,
        tasks: Iterable[str],
        outputs: Optional[Iterable[str]] = None,
        flow_num: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Spawn children of given task outputs.

        User-facing method name: set_outputs.

        Args:
            tasks: List of identifiers or task globs.
            outputs: List of outputs to spawn on.
            flow_num: Flow number to attribute the outputs.
        """
        self.schd.command_queue.put(
            (
                "force_spawn_children",
                (tasks,),
                {
                    "outputs": outputs,
                    "flow_num": flow_num
                },
            )
        )
        return (True, 'Command queued')

    def stop(
        self,
        mode: Union[str, 'StopMode'],
        cycle_point: Optional[str] = None,
        clock_time: Optional[str] = None,
        task: Optional[str] = None,
        flow_num: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Stop the workflow or specific flow from spawning any further.

        Args:
            mode: Stop mode to set
            cycle_point: Cycle point after which to stop.
            clock_time: Wallclock time after which to stop.
            task: Stop after this task succeeds.
            flow_num: The flow to stop.
    ):

        Returns:
            outcome: True if command successfully queued.
            message: Information about outcome.

        """
        self.schd.command_queue.put((
            "stop",
            (),
            filter_none({
                'mode': mode,
                'cycle_point': cycle_point,
                'clock_time': clock_time,
                'task': task,
                'flow_num': flow_num,
            }),
        )
        )
        return (True, 'Command queued')

    def force_trigger_tasks(
        self,
        tasks: Iterable[str],
        flow: Iterable[str],
        flow_wait: bool,
        flow_descr: Optional[str] = None,
    ):
        """Trigger submission of task jobs where possible.

        Args:
            tasks (list):
                List of identifiers or task globs.
            flow (list):
                Flow ownership of triggered tasks.
            flow_wait (bool):
                Wait for flows before continuing
            flow_descr (str):
                Description of new flow.

        Returns:
            tuple: (outcome, message)
            outcome (bool)
                True if command successfully queued.
            message (str)
                Information about outcome.

        """
        self.schd.command_queue.put(
            (
                "force_trigger_tasks",
                (tasks or [],),
                {
                    "flow": flow,
                    "flow_wait": flow_wait,
                    "flow_descr": flow_descr
                }
            ),
        )
        return (True, 'Command queued')

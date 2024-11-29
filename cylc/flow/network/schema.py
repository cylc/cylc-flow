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

"""GraphQL API schema via Graphene implementation."""

from copy import deepcopy
from functools import partial
import json
from operator import attrgetter
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

import graphene
from graphene import (
    ID,
    Argument,
    Boolean,
    Field,
    Float,
    InputObjectType,
    Int,
    Interface,
    Mutation,
    ObjectType,
    Schema,
    String,
)
from graphene.types.generic import GenericScalar
from graphene.utils.str_converters import to_snake_case
from graphql.type.definition import get_named_type

from cylc.flow import LOG_LEVELS
from cylc.flow.broadcast_mgr import (
    ALL_CYCLE_POINTS_STRS,
    addict,
)
from cylc.flow.data_store_mgr import (
    DELTA_ADDED,
    DELTA_UPDATED,
    FAMILIES,
    FAMILY_PROXIES,
    JOBS,
    TASK_PROXIES,
    TASKS,
)
from cylc.flow.flow_mgr import (
    FLOW_ALL,
    FLOW_NEW,
    FLOW_NONE,
)
from cylc.flow.id import Tokens
from cylc.flow.run_modes import (
    TASK_CONFIG_RUN_MODES, WORKFLOW_RUN_MODES, RunMode)
from cylc.flow.task_outputs import SORT_ORDERS
from cylc.flow.task_state import (
    TASK_STATUS_DESC,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
    TASK_STATUSES_ORDERED,
)
from cylc.flow.util import sstrip
from cylc.flow.workflow_status import StopMode


if TYPE_CHECKING:
    from enum import Enum
    from graphql import ResolveInfo
    from graphql.type.definition import (
        GraphQLList,
        GraphQLNamedType,
        GraphQLNonNull,
    )

    from cylc.flow.network.resolvers import BaseResolvers


def sort_elements(elements, args):
    """Sort iterable of elements by given attribute."""
    sort_args = args.get('sort')
    if sort_args and elements:
        keys = [
            to_snake_case(key)
            for key in sort_args.keys
        ]
        if not keys:
            raise ValueError('You must provide at least one key to sort')
        keys_not_in_schema = [
            key for key in keys if not hasattr(elements[0], key)]
        if keys_not_in_schema:
            raise ValueError(f'''The following sort keys are not in the
            schema: {', '.join(keys_not_in_schema)}''')
        # sort using the keys provided
        elements.sort(
            key=attrgetter(*keys),
            reverse=sort_args.reverse)
    return elements


PROXY_NODES = 'proxy_nodes'

# Mapping of GraphQL types to field names:
NODE_MAP = {
    'Task': TASKS,
    'TaskProxy': TASK_PROXIES,
    'Family': FAMILIES,
    'FamilyProxy': FAMILY_PROXIES,
    'Job': JOBS,
    'Node': PROXY_NODES,
}

DEF_TYPES = [
    'families',
    'family',
    'tasks',
    'task',
]


# ** Query Related **#

# Field args (i.e. for queries etc):
class SortArgs(InputObjectType):
    keys = graphene.List(String, default_value=['id'])
    reverse = Boolean(default_value=False)


STRIP_NULL_DEFAULT = Argument(
    Boolean, description="A flag that when enabled strips out those fields "
                         "not set in the protobuf object. And when this flag "
                         "is disabled the default values of Protobuf fields "
                         "are provided (boolean=false, list=[], string=\"\".")
DELTA_STORE_DEFAULT = Boolean(default_value=False)
DELTA_TYPE_DEFAULT = String(default_value='added')

JOB_ARGS = {
    'ids': graphene.List(ID, default_value=[]),
    'exids': graphene.List(ID, default_value=[]),
    'states': graphene.List(String, default_value=[]),
    'exstates': graphene.List(String, default_value=[]),
    'sort': SortArgs(default_value=None),
}

ALL_JOB_ARGS = {
    'workflows': graphene.List(ID, default_value=[]),
    'exworkflows': graphene.List(ID, default_value=[]),
    'ids': graphene.List(ID, default_value=[]),
    'exids': graphene.List(ID, default_value=[]),
    'states': graphene.List(String, default_value=[]),
    'exstates': graphene.List(String, default_value=[]),
    'sort': SortArgs(default_value=None),
}

DEF_ARGS = {
    'ids': graphene.List(ID, default_value=[]),
    'exids': graphene.List(ID, default_value=[]),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

ALL_DEF_ARGS = {
    'workflows': graphene.List(ID, default_value=[]),
    'exworkflows': graphene.List(ID, default_value=[]),
    'ids': graphene.List(ID, default_value=[]),
    'exids': graphene.List(ID, default_value=[]),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

PROXY_ARGS = {
    'ids': graphene.List(ID, default_value=[]),
    'exids': graphene.List(ID, default_value=[]),
    'states': graphene.List(String, default_value=[]),
    'exstates': graphene.List(String, default_value=[]),
    'is_held': Boolean(),
    'is_queued': Boolean(),
    'is_runahead': Boolean(),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'graph_depth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

ALL_PROXY_ARGS = {
    'workflows': graphene.List(ID, default_value=[]),
    'exworkflows': graphene.List(ID, default_value=[]),
    'ids': graphene.List(ID, default_value=[]),
    'exids': graphene.List(ID, default_value=[]),
    'states': graphene.List(String, default_value=[]),
    'exstates': graphene.List(String, default_value=[]),
    'is_held': Boolean(),
    'is_queued': Boolean(),
    'is_runahead': Boolean(),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'graph_depth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

EDGE_ARGS = {
    'ids': graphene.List(ID, default_value=[]),
    'exids': graphene.List(ID, default_value=[]),
    'states': graphene.List(String, default_value=[]),
    'exstates': graphene.List(String, default_value=[]),
    'sort': SortArgs(default_value=None),
}

ALL_EDGE_ARGS = {
    'workflows': graphene.List(ID, default_value=[]),
    'exworkflows': graphene.List(ID, default_value=[]),
    'sort': SortArgs(default_value=None),
}

NODES_EDGES_ARGS = {
    'ids': graphene.List(ID, default_value=[]),
    'exids': graphene.List(ID, default_value=[]),
    'states': graphene.List(String, default_value=[]),
    'exstates': graphene.List(String, default_value=[]),
    'is_held': Boolean(),
    'is_queued': Boolean(),
    'is_runahead': Boolean(),
    'distance': Int(default_value=1),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

NODES_EDGES_ARGS_ALL = {
    'workflows': graphene.List(ID, default_value=[]),
    'exworkflows': graphene.List(ID, default_value=[]),
    'ids': graphene.List(ID, default_value=[]),
    'exids': graphene.List(ID, default_value=[]),
    'states': graphene.List(String, default_value=[]),
    'exstates': graphene.List(String, default_value=[]),
    'is_held': Boolean(),
    'is_queued': Boolean(),
    'is_runahead': Boolean(),
    'distance': Int(default_value=1),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

# Resolvers are used to collate data needed for query resolution.
# Treated as implicit static methods;
# https://docs.graphene-python.org/en/latest/types
# /objecttypes/#implicit-staticmethod
# they can exist inside or outside the query object types.
#
# Here we define them outside the queries so they can be used with
# multiple resolution calls, both at root query or object field level.
#
# The first argument has a naming convention;
# https://docs.graphene-python.org/en/latest/types
# /objecttypes/#naming-convention
# with name 'root' used here, it provides context to the resolvers.


# Resolvers:

def field_name_from_type(
    obj_type: 'Union[GraphQLNamedType, GraphQLList, GraphQLNonNull]'
) -> str:
    """Return the field name for given a GraphQL type.

    If the type is a list or non-null, the base field is extracted.
    """
    named_type = cast('GraphQLNamedType', get_named_type(obj_type))
    try:
        return NODE_MAP[named_type.name]
    except KeyError:
        raise ValueError(f"'{named_type.name}' is not a node type") from None


def get_resolvers(info: 'ResolveInfo') -> 'BaseResolvers':
    """Return the resolvers from the context."""
    return cast('dict', info.context)['resolvers']


def process_resolver_info(
    root: Optional[Any], info: 'ResolveInfo', args: Dict[str, Any]
) -> Tuple[str, Optional[Any]]:
    """Set and gather info for resolver."""
    # Add the subscription id to the resolver context
    # to know which delta-store to use."""
    if 'backend_sub_id' in info.variable_values:
        args['sub_id'] = info.variable_values['backend_sub_id']

    field_name: str = to_snake_case(info.field_name)
    # root is the parent data object.
    # i.e. PbWorkflow or list of IDs graphene.List(String)
    if isinstance(root, dict):
        root_value = root.get(field_name, None)
    else:
        root_value = getattr(root, field_name, None)

    return (field_name, root_value)


def get_native_ids(field_ids):
    """Collect IDs into list form."""
    if isinstance(field_ids, str):
        return [field_ids]
    if isinstance(field_ids, dict):
        return list(field_ids)
    return field_ids


async def get_workflows(root, info: 'ResolveInfo', **args):
    """Get filtered workflows."""

    _, workflow = process_resolver_info(root, info, args)
    if workflow is not None:
        args['ids'] = [workflow.id]

    args['workflows'] = [Tokens(w_id) for w_id in args['ids']]
    args['exworkflows'] = [Tokens(w_id) for w_id in args['exids']]
    resolvers = get_resolvers(info)
    return await resolvers.get_workflows(args)


async def get_workflow_by_id(root, info: 'ResolveInfo', **args):
    """Return single workflow element."""

    _, workflow = process_resolver_info(root, info, args)
    if workflow is not None:
        args['id'] = workflow.id

    args['workflow'] = args['id']
    resolvers = get_resolvers(info)
    return await resolvers.get_workflow_by_id(args)


async def get_nodes_all(
    root: Optional[Any], info: 'ResolveInfo', **args
):
    """Resolver for returning job, task, family nodes"""

    _, field_ids = process_resolver_info(root, info, args)

    if field_ids:
        if isinstance(field_ids, str):
            field_ids = [field_ids]
        elif isinstance(field_ids, dict):
            field_ids = list(field_ids)
        args['ids'] = field_ids
    elif field_ids == []:
        return []

    node_field_name = field_name_from_type(info.return_type)

    for arg in ('ids', 'exids'):
        if node_field_name in DEF_TYPES:
            # namespace nodes don't fit into the universal ID scheme so must
            # be tokenised manually
            args[arg] = [
                Tokens(
                    cycle=None,
                    task=task,
                    job=None,
                )
                for task in args[arg]
            ]
        else:
            # live objects can be represented by a universal ID
            args[arg] = [Tokens(n_id, relative=True) for n_id in args[arg]]
    for arg in ('workflows', 'exworkflows'):
        args[arg] = [Tokens(w_id) for w_id in args[arg]]
    resolvers = get_resolvers(info)
    return await resolvers.get_nodes_all(node_field_name, args)


async def get_nodes_by_ids(
    root: Optional[Any], info: 'ResolveInfo', **args
):
    """Resolver for returning job, task, family node"""
    field_name, field_ids = process_resolver_info(root, info, args)

    resolvers = get_resolvers(info)
    if field_ids == []:
        parent_id = getattr(root, 'id', None)
        # Find node ids from parent
        if parent_id:
            parent_args = deepcopy(args)
            parent_args.update(
                {'id': parent_id, 'delta_store': False}
            )
            parent_type = cast(
                'GraphQLNamedType', get_named_type(info.parent_type)
            )
            if parent_type.name in NODE_MAP:
                parent = await resolvers.get_node_by_id(
                    NODE_MAP[parent_type.name], parent_args
                )
            else:
                parent = await resolvers.get_workflow_by_id(parent_args)
            field_ids = getattr(parent, field_name, None)
        if not field_ids:
            return []
    if field_ids:
        args['native_ids'] = get_native_ids(field_ids)

    node_field_name = field_name_from_type(info.return_type)

    args['ids'] = [Tokens(n_id, relative=True) for n_id in args['ids']]
    args['exids'] = [Tokens(n_id, relative=True) for n_id in args['exids']]
    return await resolvers.get_nodes_by_ids(node_field_name, args)


async def get_node_by_id(
    root: Optional[Any], info: 'ResolveInfo', **args
):
    """Resolver for returning job, task, family node"""

    field_name, field_id = process_resolver_info(root, info, args)

    if field_name == 'source_node':
        field_name = 'source'
    elif field_name == 'target_node':
        field_name = 'target'

    resolvers = get_resolvers(info)
    if args.get('id') is None:
        field_id = getattr(root, field_name, None)
        # Find node id from parent
        if not field_id:
            parent_id = getattr(root, 'id', None)
            if parent_id:
                parent_args = deepcopy(args)
                parent_args.update(
                    {'id': parent_id, 'delta_store': False}
                )
                args['id'] = parent_id
                parent = await resolvers.get_node_by_id(
                    field_name_from_type(info.parent_type),
                    parent_args
                )
                field_id = getattr(parent, field_name, None)
        if field_id:
            args['id'] = field_id
        else:
            return None

    return await resolvers.get_node_by_id(
        field_name_from_type(info.return_type), args
    )


async def get_edges_all(root, info: 'ResolveInfo', **args):
    """Get all edges from the store filtered by args."""

    process_resolver_info(root, info, args)

    args['workflows'] = [
        Tokens(w_id) for w_id in args['workflows']
    ]
    args['exworkflows'] = [
        Tokens(w_id) for w_id in args['exworkflows']
    ]
    resolvers = get_resolvers(info)
    return await resolvers.get_edges_all(args)


async def get_edges_by_ids(root, info: 'ResolveInfo', **args):
    """Get all edges from the store by id lookup filtered by args."""

    _, field_ids = process_resolver_info(root, info, args)

    if field_ids:
        args['native_ids'] = get_native_ids(field_ids)
    elif field_ids == []:
        return []

    resolvers = get_resolvers(info)
    return await resolvers.get_edges_by_ids(args)


async def get_nodes_edges(root, info: 'ResolveInfo', **args):
    """Resolver for returning job, task, family nodes"""

    process_resolver_info(root, info, args)

    if hasattr(root, 'id'):
        args['workflows'] = [Tokens(root.id)]
        args['exworkflows'] = []
    else:
        args['workflows'] = [
            Tokens(w_id) for w_id in args['workflows']
        ]
        args['exworkflows'] = [
            Tokens(w_id) for w_id in args['exworkflows']
        ]

    args['ids'] = [Tokens(n_id) for n_id in args['ids']]
    args['exids'] = [Tokens(n_id) for n_id in args['exids']]

    resolvers = get_resolvers(info)
    root_nodes = await resolvers.get_nodes_all(TASK_PROXIES, args)
    return await resolvers.get_nodes_edges(root_nodes, args)


def resolve_state_totals(root, info, **args):
    state_totals = dict.fromkeys(TASK_STATUSES_ORDERED, 0)
    # Update with converted protobuf map container
    state_totals.update(
        dict(getattr(root, to_snake_case(info.field_name), {})))
    return state_totals


def resolve_state_tasks(root, info, **args):
    data = dict(getattr(root, to_snake_case(info.field_name), {}))
    return {
        state: list(data[state].task_proxies)
        for state in args['states']
        if state in data}


async def resolve_broadcasts(root, info: 'ResolveInfo', **args):
    """Resolve and parse broadcasts from JSON."""
    broadcasts = json.loads(
        getattr(root, to_snake_case(info.field_name), '{}'))
    resolvers = get_resolvers(info)

    if not args['ids']:
        return broadcasts

    result: Dict[str, dict] = {}
    t_type = NODE_MAP['Task']
    t_args: Dict[str, list] = {'workflows': [Tokens(root.id)]}
    for n_id in args['ids']:
        tokens = Tokens(n_id)
        point_string = tokens['cycle']
        name = tokens['task']
        if point_string is None:
            point_string = '*'
        for cycle in set(ALL_CYCLE_POINTS_STRS + [point_string]):
            if cycle not in broadcasts:
                continue
            t_args['ids'] = [(None, None, None, name, None, None)]
            tasks = await resolvers.get_nodes_all(t_type, t_args)
            for namespace in {ns for t in tasks for ns in t.namespace}:
                if namespace in broadcasts[cycle]:
                    addict(
                        result,
                        {cycle: {namespace: broadcasts[cycle][namespace]}}
                    )
    return result


def resolve_json_dump(root, info, **args):
    field = getattr(root, to_snake_case(info.field_name), '{}') or '{}'
    return json.loads(field)


def resolve_mapping_to_list(root, info, **args):
    field = getattr(root, to_snake_case(info.field_name), {}) or {}
    mapping = {
        key: field[key]
        for key in args.get('sort_order', [])
        if key in field}
    mapping.update(field)
    satisfied = args.get('satisfied')
    elements = sort_elements(
        [
            val
            for val in mapping.values()
            if satisfied is None or val.satisfied is satisfied
        ], args)
    limit = args['limit']
    if elements and limit:
        elements = elements[:limit]
    return elements


# Types:
class NodeMeta(ObjectType):
    class Meta:
        description = sstrip("""
            Meta data fields, including custom fields in a generic user-defined
            dump.
        """)
    title = String(default_value=None)
    description = String(default_value=None)
    URL = String(default_value=None)
    user_defined = GenericScalar(resolver=resolve_json_dump)


class TimeZone(ObjectType):
    class Meta:
        description = 'Time zone info.'
    hours = Int()
    minutes = Int()
    string_basic = String()
    string_extended = String()


# The run mode for the workflow.
WorkflowRunMode = graphene.Enum(
    'WorkflowRunMode',
    [(m.capitalize(), m) for m in WORKFLOW_RUN_MODES],
    description=lambda x: RunMode(x.value).describe() if x else None,
)

# The run mode for the task.
TaskRunMode = graphene.Enum(
    'TaskRunMode',
    [(m.capitalize(), m) for m in TASK_CONFIG_RUN_MODES],
    description=lambda x: RunMode(x.value).describe() if x else None,
)


class Workflow(ObjectType):
    class Meta:
        description = 'Global workflow info.'
    id = ID()  # noqa: A003 (required for definition)
    name = String(
        description='The workflow ID with the ~user/ prefix removed.',
    )
    status = String(
        description='The workflow status e.g. `running`.',
    )
    status_msg = String(
        description='A description of the workflow status.',
    )
    host = String(
        description='The host where the scheduler process is running.',
    )
    port = Int(
        description='The port for sending ZMQ requests to the scheduler.',
    )
    pub_port = Int(
        description=sstrip('''
            The port for subscribing to ZMQ updates from the scheduler.
        '''),
    )
    owner = String(
        description='The user account that the workflow is running under.',
    )
    tasks = graphene.List(
        lambda: Task,
        description="Task definitions.",
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids,
    )
    families = graphene.List(
        lambda: Family,
        description="Family definitions.",
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids,
    )
    task_proxies = graphene.List(
        lambda: TaskProxy,
        description="Task instances.",
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids,
    )
    family_proxies = graphene.List(
        lambda: FamilyProxy,
        description="Family instances.",
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids,
    )
    jobs = graphene.List(
        lambda: Job,
        description="Jobs.",
        args=JOB_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids,
    )
    edges = Field(
        lambda: Edges,
        args=EDGE_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        description="Graph edges.",
    )
    nodes_edges = Field(
        lambda: NodesEdges,
        args=NODES_EDGES_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_edges,
        description='Graph nodes and edges.'
    )
    api_version = Int(
        description='The Cylc scheduler communication protocol version number.'
    )
    cylc_version = String(
        description='The Cylc version this workflow is running under.',
    )
    last_updated = Float(
        description='The time of the most recent state change in the workflow.'
    )
    meta = Field(
        NodeMeta,
        description="The workflow's `[meta]` section.",
    )
    newest_active_cycle_point = String(
        description='The newest cycle point which has active tasks.'
    )
    oldest_active_cycle_point = String(
        description='The oldest cycle point which has active tasks.'
    )
    reloaded = Boolean(
        description=sstrip('''
            When subscribing to workflow updates, this field is `True` if the
            update relates to a workflow reload.
        '''),
    )
    run_mode = String(
        description="The scheduler's run-mode e.g. `live`.",
    )
    is_held_total = Int(
        description='The number of "held" tasks.',
    )
    is_queued_total = Int(
        description='The number of queued tasks.',
    )
    is_runahead_total = Int(
        description=sstrip('''
            The number of tasks which are held back by the runahead limit.
        ''')
    )
    state_totals = GenericScalar(
        resolver=resolve_state_totals,
        description='The number of tasks in each state as a JSON object.',
    )
    latest_state_tasks = GenericScalar(
        states=graphene.List(
            String,
            description="List of task states to show.",
            default_value=TASK_STATUSES_ORDERED),
        resolver=resolve_state_tasks,
        description='The latest tasks to have entered each task state.',
    )
    workflow_log_dir = String(
        description="The path to the workflow's run directory.",
    )
    time_zone_info = Field(
        TimeZone,
        description='The scheduler time zone.',
    )
    tree_depth = Int()  # TODO: what is this? write description
    ns_def_order = graphene.List(
        String,
        description=sstrip('''
            Namespace definition order.

            The order in which tasks were defined in the workflow
            configuration.
        '''),
    )
    job_log_names = graphene.List(
        # TODO: remove, see https://github.com/cylc/cylc-flow/issues/5610
        String,
        description='Deprecated, do not use this.',
    )
    states = graphene.List(
        String,
        description=sstrip('''
            The task states present in the workflow.

            Similar to stateTotals.
        '''),
    )
    broadcasts = GenericScalar(
        ids=graphene.List(
            ID,
            description=sstrip('''
                Node IDs, cycle point and/or-just family/task namespace.

                E.g: `["1234/foo", "1234/FAM", "*/FAM"]`
            '''),
            default_value=[]
        ),
        resolver=resolve_broadcasts,
        description='Any active workflow broadcasts.'
    )
    pruned = Boolean()  # TODO: what is this? write description
    n_edge_distance = Int(
        description=sstrip('''
            The maximum graph distance (n) from an active node
            of the data-store graph window.
        '''),
    )


class RuntimeSetting(ObjectType):
    """Key = value setting for a `[runtime][<namespace>]` configuration."""
    key = String(default_value=None)
    value = String(default_value=None)


class Runtime(ObjectType):
    class Meta:
        description = sstrip("""
            Subset of runtime fields.

            Existing on 3 different node types:
            - Task/family definition (from the flow.cylc file)
            - Task/family cycle instance (includes any broadcasts on top
              of the definition)
            - Job (a record of what was run for a particular submit)
        """)
    platform = String(default_value=None)
    script = String(default_value=None)
    completion = String(default_value=None)
    init_script = String(default_value=None)
    env_script = String(default_value=None)
    err_script = String(default_value=None)
    exit_script = String(default_value=None)
    pre_script = String(default_value=None)
    post_script = String(default_value=None)
    work_sub_dir = String(default_value=None)
    execution_polling_intervals = String(default_value=None)
    execution_retry_delays = String(default_value=None)
    execution_time_limit = String(default_value=None)
    submission_polling_intervals = String(default_value=None)
    submission_retry_delays = String(default_value=None)
    directives = graphene.List(RuntimeSetting, resolver=resolve_json_dump)
    environment = graphene.List(RuntimeSetting, resolver=resolve_json_dump)
    outputs = graphene.List(RuntimeSetting, resolver=resolve_json_dump)
    run_mode = TaskRunMode(default_value=TaskRunMode.Live.name)


RUNTIME_FIELD_TO_CFG_MAP = {
    **{
        k: k.replace('_', ' ') for k in Runtime.__dict__
        if not k.startswith('_')
    },
    'init_script': 'init-script',
    'env_script': 'env-script',
    'err_script': 'err-script',
    'exit_script': 'exit-script',
    'pre_script': 'pre-script',
    'post_script': 'post-script',
    'work_sub_dir': 'work sub-directory',
}
"""Map GQL Runtime fields' names to workflow config setting names."""


def runtime_schema_to_cfg(runtime: dict) -> dict:
    """Covert GQL Runtime field names to workflow config setting names and
    perform any necessary processing on the values."""
    # We have to manually lowercase the run_mode field because we don't define
    # a proper schema for BroadcastSetting (it's just GenericScalar) so
    # Graphene has no way to know that it should be a TaskRunMode enum.
    return {
        RUNTIME_FIELD_TO_CFG_MAP.get(key, key): (
            value.lower() if key == 'run_mode' else value
        )
        for key, value in runtime.items()
    }


class Job(ObjectType):
    class Meta:
        description = "Jobs."

    id = ID()  # noqa: A003 (required for definition)
    submit_num = Int(
        description='The submission number for this job, starts at 1.',
    )
    state = String(
        description='The job state e.g. `running` or `succeeded`.',
    )
    name = String(
        description='The name of the task which submitted this job.',
    )
    cycle_point = String(
        description='The cycle of the task which submitted this job.',
    )
    task_proxy = Field(
        lambda: TaskProxy,
        description="The TaskProxy of the task which submitted this job.",
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    submitted_time = String(
        description='The time this job was submitted to the job runner.',
    )
    started_time = String(
        description='The time this job started running (if it has yet).',
    )
    finished_time = String(
        description='The time this job finished running (if it has yet).',
    )
    job_id = ID(
        description='The ID of this job in the job runner it was submitted to.'
    )
    job_runner_name = String(
        description='The job runner this job was submitted to.',
    )
    execution_time_limit = Float(
        description='The time limit for this job if configured.',
    )
    platform = String(
        description='The Cylc platform this job was submitted to.',
    )
    job_log_dir = String(
        description="The path to the job's log directory.",
    )
    messages = graphene.List(
        String,
        description='The list of task messages generated by this job.',
    )
    runtime = Field(
        Runtime,
        description=sstrip('''
            The `[runtime]` configuration of the task which submitted this job.
        '''),
    )


class Task(ObjectType):
    class Meta:
        description = sstrip("""
            Task definitions.

            These are the task "definitions" as they appear in the
            configuration as opposed to task "instances" which you will find
            in the `TaskProxies` field.
        """)

    id = ID()  # noqa: A003 (required for definition)
    name = String(
        description='The task name.'
    )
    meta = Field(
        NodeMeta,
        description="The task's `[meta]` section.",
    )
    runtime = Field(
        Runtime,
        description="The task's `[runtime]` section.",
    )
    mean_elapsed_time = Float(
        description="The task's average runtime."
    )
    depth = Int(
        description='The family inheritance depth.'
    )
    proxies = graphene.List(
        lambda: TaskProxy,
        description="Associated cycle point proxies",
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    parents = graphene.List(
        lambda: Family,
        description="Family definition parent.",
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    namespace = graphene.List(String)
    first_parent = Field(
        lambda: Family,
        description="Task first parent.",
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)


class PollTask(ObjectType):
    class Meta:
        description = 'Polling task edge.'
    local_proxy = ID()
    workflow = String()
    remote_proxy = ID()
    req_state = String()
    graph_string = String()


class Condition(ObjectType):
    class Meta:
        description = 'Prerequisite conditions.'
    task_id = String()
    task_proxy = Field(
        lambda: TaskProxy,
        description='Associated Task Proxy.',
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    expr_alias = String()
    req_state = String()
    satisfied = Boolean()
    message = String()

    def resolve_task_id(root, info, **args):
        return getattr(root, 'task_proxy', None)


class Prerequisite(ObjectType):
    class Meta:
        description = 'Task prerequisite.'
    expression = String()
    conditions = graphene.List(
        Condition,
        description='Condition monomers of a task prerequisites.'
    )
    cycle_points = graphene.List(String)
    satisfied = Boolean()


class Output(ObjectType):
    class Meta:
        description = 'Task output.'
    label = String()
    message = String()
    satisfied = Boolean()
    time = Float()


class OutputLabel(String):
    """Task output, e.g. `succeeded`."""


class PrerequisiteString(String):
    """A task prerequisite, e.g. `2040/foo:succeeded`."""


class XTrigger(ObjectType):
    class Meta:
        description = 'Task trigger.'
    id = String()  # noqa: A003 (required for definition)
    label = String()
    message = String()
    satisfied = Boolean()
    time = Float()


class TaskProxy(ObjectType):
    class Meta:
        description = 'Task cycle instance.'
    id = ID()  # noqa: A003 (required for schema definition)
    task = Field(
        Task,
        description="The task definition relating to this task instance.",
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    runtime = Field(
        Runtime,
        description="This task's `[runtime]` section.",
    )
    state = String(
        description='The task state e.g. `running`.',
    )
    name = String(
        description="The task's name.",
    )
    cycle_point = String(
        description="The task's cycle point.",
    )
    namespace = graphene.List(
        String,
        description='The inheritance order for this task.',
    )
    is_held = Boolean(
        description='True if this task is "held".',
    )
    is_queued = Boolean(
        description=sstrip('''
            True if this task is "queued".

            This relates to Cylc's internal task queues, not a job runner
            queue.
        '''),
    )
    is_runahead = Boolean(
        description='True if this task is held back by the "runahead limit".',
    )
    flow_nums = String(
        description='The flows this task instance belongs to.',
    )
    flow_wait = Boolean(
        description=sstrip('''
            True if this task will wait for an approaching flow before spawning
            outputs downstream.
        '''),
    )
    depth = Int(
        description='The family inheritance depth.',
    )
    graph_depth = Int(
        description=sstrip('''
            The n-window graph edge depth from closet active task(s).
        '''),
    )
    job_submits = Int(
        description='The number of job submissions for this task instance.',
    )
    outputs = graphene.List(
        Output,
        description="Outputs this task instance has generated.",
        sort=SortArgs(default_value=None),
        sort_order=graphene.List(
            String,
            default_value=list(SORT_ORDERS)
        ),
        limit=Int(default_value=0),
        satisfied=Boolean(),
        resolver=resolve_mapping_to_list)
    external_triggers = graphene.List(
        XTrigger,
        description="Task external trigger prerequisites.",
        sort=SortArgs(default_value=None),
        sort_order=graphene.List(String),
        limit=Int(default_value=0),
        satisfied=Boolean(),
        resolver=resolve_mapping_to_list)
    xtriggers = graphene.List(
        XTrigger,
        description="Task xtrigger prerequisites.",
        sort=SortArgs(default_value=None),
        sort_order=graphene.List(String),
        limit=Int(default_value=0),
        satisfied=Boolean(),
        resolver=resolve_mapping_to_list)
    extras = GenericScalar(
        # TODO: what is this? write description
        resolver=resolve_json_dump,
    )
    prerequisites = graphene.List(
        Prerequisite,
        description='The prerequisites of this task.',
    )
    jobs = graphene.List(
        Job,
        description="Jobs.",
        args=JOB_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids,
    )
    parents = graphene.List(
        lambda: FamilyProxy,
        description="Task parents (i.e. families).",
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids,
    )
    first_parent = Field(
        lambda: FamilyProxy,
        description="The task's first parent (i.e. its containing family).",
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id,
    )
    ancestors = graphene.List(
        lambda: FamilyProxy,
        description="First parent ancestors (i.e. inheritance hierarchy).",
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids,
    )


class Family(ObjectType):
    class Meta:
        description = 'Task definition, static fields.'
    id = ID()  # noqa: A003 (required for schema definition)
    name = String()
    meta = Field(NodeMeta)
    runtime = Field(Runtime)
    depth = Int()
    proxies = graphene.List(
        lambda: FamilyProxy,
        description='Associated cycle point proxies.',
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    parents = graphene.List(
        lambda: Family,
        description='Family definition parent.',
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    child_tasks = graphene.List(
        Task,
        description='Descendant definition tasks.',
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    child_families = graphene.List(
        lambda: Family,
        description='Descendant desc families.',
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    first_parent = Field(
        lambda: Family,
        description='Family first parent.',
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)


class FamilyProxy(ObjectType):
    class Meta:
        description = 'Family composite.'
    id = ID()  # noqa: A003 (required for schema definition)
    cycle_point = String()
    # name & namespace for filtering/sorting
    name = String()
    family = Field(
        Family,
        description='Family definition.',
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    runtime = Field(Runtime)
    state = String()
    states = graphene.List(String)
    state_totals = GenericScalar(resolver=resolve_state_totals)
    is_held = Boolean()
    is_held_total = Int()
    is_queued = Boolean()
    is_queued_total = Int()
    is_runahead = Boolean()
    is_runahead_total = Int()
    depth = Int()
    graph_depth = Int(
        description=sstrip('''
            The n-window graph edge smallest child task/family depth
            from closet active task(s).
        '''),
    )
    child_tasks = graphene.List(
        TaskProxy,
        description='Descendant task proxies.',
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    child_families = graphene.List(
        lambda: FamilyProxy,
        description='Descendant family proxies.',
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    first_parent = Field(
        lambda: FamilyProxy,
        description='Task first parent.',
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    ancestors = graphene.List(
        lambda: FamilyProxy,
        description='First parent ancestors.',
        args=PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)


class Node(graphene.Union):
    class Meta:
        types = (TaskProxy, FamilyProxy)

    @classmethod
    def resolve_type(cls, instance, info):
        if hasattr(instance, 'task'):
            return TaskProxy
        return FamilyProxy


class Edge(ObjectType):
    class Meta:
        description = 'Dependency edge task/family proxies.'
    id = ID()  # noqa: A003 (required for schema definition)
    source = ID()
    source_node = Field(
        Node,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    target = ID()
    target_node = Field(
        Node,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    suicide = Boolean()
    cond = Boolean()


class Edges(ObjectType):
    class Meta:
        description = 'Dependency edge.'
    edges = graphene.List(
        Edge,
        args=EDGE_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_edges_by_ids)
    workflow_polling_tasks = graphene.List(PollTask)
    leaves = graphene.List(String)
    feet = graphene.List(String)


class NodesEdges(ObjectType):
    class Meta:
        description = 'Related Nodes & Edges.'
    nodes = graphene.List(
        TaskProxy,
        description='Task nodes from and including root.')
    edges = graphene.List(
        Edge,
        description='Edges associated with the nodes.')


# Query declaration
class Queries(ObjectType):
    class Meta:
        description = 'Multi-Workflow root level queries.'
    workflows = graphene.List(
        Workflow,
        description=Workflow._meta.description,
        ids=graphene.List(ID, default_value=[]),
        exids=graphene.List(ID, default_value=[]),
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_workflows)
    job = Field(
        Job,
        description=Job._meta.description,
        id=ID(required=True),
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_node_by_id)
    jobs = graphene.List(
        Job,
        description=Job._meta.description,
        args=ALL_JOB_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_nodes_all)
    task = Field(
        Task,
        description=Task._meta.description,
        id=ID(required=True),
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_node_by_id)
    tasks = graphene.List(
        Task,
        description=Task._meta.description,
        args=ALL_DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_nodes_all)
    task_proxy = Field(
        TaskProxy,
        description=TaskProxy._meta.description,
        id=ID(required=True),
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_node_by_id)
    task_proxies = graphene.List(
        TaskProxy,
        description=TaskProxy._meta.description,
        args=ALL_PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_nodes_all)
    family = Field(
        Family,
        description=Family._meta.description,
        id=ID(required=True),
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_node_by_id)
    families = graphene.List(
        Family,
        description=Family._meta.description,
        args=ALL_DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_nodes_all)
    family_proxy = Field(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        id=ID(required=True),
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_node_by_id)
    family_proxies = graphene.List(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        args=ALL_PROXY_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_nodes_all)
    edges = graphene.List(
        Edge,
        description=Edge._meta.description,
        args=ALL_EDGE_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_edges_all)
    nodes_edges = Field(
        NodesEdges,
        description=NodesEdges._meta.description,
        args=NODES_EDGES_ARGS_ALL,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_nodes_edges)


# ** Mutation Related ** #


# Generic containers
class GenericResponse(ObjectType):
    class Meta:
        description = 'Container for command queued response.'

    result = GenericScalar()


# Mutators are used to call the internals of the parent program in the
# resolution of mutation requests (or can make external calls themselves).
# Like query resolvers (read above), they are treated as implicit
# static methods, with object context pass in as the first argument.

# Mutators:

async def mutator(
    root: Optional[Any],
    info: 'ResolveInfo',
    *,
    command: Optional[str] = None,
    workflows: Optional[List[str]] = None,
    exworkflows: Optional[List[str]] = None,
    **kwargs: Any
) -> GenericResponse:
    """Call the resolver method that act on the workflow service
    via the internal command queue.

    This is what a mutation's Meta.resolver should be set to
    (or the mutation's mutate() method).

    Args:
        root: Parent field (if any) value object.
        info: GraphQL execution info.
        command: Mutation command name (name of method of
            cylc.flow.network.resolvers.Resolvers or Scheduler command_<name>
            method). If None, uses mutation class name converted to snake_case.
        workflows: List of workflow IDs.
        exworkflows: List of workflow IDs.

    """
    if command is None:
        command = to_snake_case(info.field_name)
    if workflows is None:
        workflows = []
    if exworkflows is None:
        exworkflows = []
    w_args = {
        'workflows': [Tokens(w_id) for w_id in workflows],
        'exworkflows': [Tokens(w_id) for w_id in exworkflows]
    }
    if kwargs.get('args', False):
        kwargs.update(kwargs.get('args', {}))
        kwargs.pop('args')
    resolvers = get_resolvers(info)
    meta = info.context.get('meta')  # type: ignore[union-attr]
    res = await resolvers.mutator(info, command, w_args, kwargs, meta)
    return GenericResponse(result=res)


# Input types:

class WorkflowID(String):
    """A registered workflow."""


class CyclePoint(String):
    """An integer or date-time cyclepoint."""


class CyclePointGlob(String):
    """A glob for integer or date-time cyclepoints.

    The wildcard character (`*`) can be used to perform globbing.
    For example `2000*` might match `2000-01-01T00:00Z`.

    """


class RuntimeConfiguration(String):
    """A configuration item for a task or family e.g. `script`."""


class BroadcastMode(graphene.Enum):
    Set = cast('Enum', 'put_broadcast')
    Clear = cast('Enum', 'clear_broadcast')
    Expire = cast('Enum', 'expire_broadcast')

    @property
    def description(self):
        if self == BroadcastMode.Set:
            return 'Create a new broadcast.'
        if self == BroadcastMode.Clear:
            return (
                'Clear existing broadcasts globally or for specified'
                ' cycle points and namespaces if provided.'
            )
        if self == BroadcastMode.Expire:
            return (
                'Clear all broadcasts for cycle points earlier than the'
                ' provided cutoff.'
            )
        return ''


class BroadcastSetting(GenericScalar):
    """A `[runtime]` configuration for a namespace.

    Should be a `key=value` pair where sections are wrapped with square
    brackets.

    Examples:
        script=true
        [environment]ANSWER=42

    Nested sections should only have one set of square brackets e.g:

        [section][subsection][subsubsection]=value

    """


class BroadcastCyclePoint(graphene.String):
    """A cycle point or `*`."""
    # (broadcast supports either of those two but not cycle point globs)


class TaskStatus(graphene.Enum):
    """The status of a task in a workflow."""

    # NOTE: this is an enumeration purely for the GraphQL schema
    # TODO: the task statuses should be formally declared in a Python
    #       enumeration rendering this class unnecessary
    Waiting = TASK_STATUS_WAITING
    Expired = TASK_STATUS_EXPIRED
    Preparing = TASK_STATUS_PREPARING
    SubmitFailed = TASK_STATUS_SUBMIT_FAILED
    Submitted = TASK_STATUS_SUBMITTED
    Running = TASK_STATUS_RUNNING
    Failed = TASK_STATUS_FAILED
    Succeeded = TASK_STATUS_SUCCEEDED

    @property
    def description(self):
        return TASK_STATUS_DESC.get(self.value, '')


class TaskState(InputObjectType):
    """The state of a task, a combination of status and other fields."""

    status = TaskStatus()
    is_held = Boolean(description=sstrip('''
        If a task is held no new job submissions will be made.
    '''))
    is_queued = Boolean(description=sstrip('''
        Task is queued for job submission.
    '''))
    is_runahead = Boolean(description=sstrip('''
        Task is runahead limited.
    '''))


class TaskName(String):
    """The name a task.

    * Must be a task not a family.
    * Does not include the cycle point.
    * Any parameters must be expanded (e.g. can't be `foo<bar>`).
    """


class NamespaceName(String):
    """The name of a task or family."""


class NamespaceIDGlob(String):
    """A glob search for an active task or family.

    Can use the wildcard character (`*`), e.g `foo*` might match `foot`.
    """


class TaskID(String):
    """The name of an active task."""


class JobID(String):
    """A job submission from an active task."""


class TimePoint(String):
    """A date-time in the ISO8601 format."""


LogLevels = graphene.Enum(
    'LogLevels',
    list(LOG_LEVELS.items()),
    description=lambda x: (
        f'Logging level: {x.name} = {x.value}.'
        if x else ''
    )
)


class WorkflowStopMode(graphene.Enum):
    """The mode used to stop a running workflow."""

    # NOTE: using a different enum because:
    # * Graphene requires special enums.
    # * We only want to offer a subset of stop modes (REQUEST_* only).

    Clean = cast('Enum', StopMode.REQUEST_CLEAN.value)
    Kill = cast('Enum', StopMode.REQUEST_KILL.value)
    Now = cast('Enum', StopMode.REQUEST_NOW.value)
    NowNow = cast('Enum', StopMode.REQUEST_NOW_NOW.value)

    @property
    def description(self):
        return StopMode(self.value).describe()


class Flow(String):
    __doc__ = (
        f"""An integer or one of {FLOW_ALL}, {FLOW_NEW} or {FLOW_NONE}."""
    )


# Mutations:

class Broadcast(Mutation):
    class Meta:
        description = sstrip('''
            Override `[runtime]` configurations in a running workflow.

            Uses for broadcast include making temporary changes to task
            behaviour, and task-to-downstream-task communication via
            environment variables.

            A broadcast can set/override any `[runtime]` configuration for all
            cycles or for a specific cycle. If a task is affected by
            specific-cycle and all-cycle broadcasts at the same time, the
            specific takes precedence.

            Broadcasts can also target all tasks, specific tasks or families of
            tasks. If a task is affected by broadcasts to multiple ancestor
            namespaces (tasks it inherits from), the result is determined by
            normal `[runtime]` inheritance.

            Broadcasts are applied at the time of job submission.

            Broadcasts persist, even across restarts. Broadcasts made to
            specific cycle points will expire when the cycle point is older
            than the oldest active cycle point in the workflow.

            Active broadcasts can be revoked using the "clear" mode.
            Any broadcasts matching the specified cycle points and
            namespaces will be revoked.

            Note: a "clear" broadcast for a specific cycle or namespace does
            *not* clear all-cycle or all-namespace broadcasts.

            Valid for: paused, running workflows.
        ''')
        resolver = mutator

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)

        mode = BroadcastMode(
            # use the enum name as the default value
            # https://github.com/graphql-python/graphql-core-legacy/issues/166
            default_value=BroadcastMode.Set.name,
            description='What type of broadcast is this?',
            required=True
        )
        cycle_points = graphene.List(
            BroadcastCyclePoint,
            description=sstrip('''
                List of cycle points to target (or `*` to cancel all all-cycle
                broadcasts without canceling all specific-cycle broadcasts).
            '''),
            default_value=['*'])
        namespaces = graphene.List(
            NamespaceName,
            description='List of namespaces (tasks or families) to target.',
            default_value=['root']
        )
        settings = graphene.List(
            BroadcastSetting,
            description=sstrip('''
                The `[runtime]` configuration to override with this broadcast
                (e.g. `script = true` or `[environment]ANSWER=42`).
            '''),
            # e.g. `{environment: {variable_name: "value",. . .}. . .}`.
        )
        cutoff = CyclePoint(
            description=(
                'Clear broadcasts earlier than cutoff cycle point.'
                ' (for use with "Expire" mode).'
            )
        )

        # TODO: work out how to implement this feature, it needs to be
        #       handled client-side which makes it slightly awkward in
        #       api-on-the-fly land

        # files = graphene.List(
        #    String,
        #    description=sstrip('''
        #        File with config to broadcast. Can be used multiple times
        #    ''')
        # )

    result = GenericScalar()


class SetHoldPoint(Mutation):
    class Meta:
        description = sstrip('''
            Set workflow hold after cycle point. All tasks after this point
            will be held.

            Valid for: paused, running workflows.
        ''')
        resolver = mutator

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)
        point = CyclePoint(
            description='Hold all tasks after the specified cycle point.',
            required=True
        )

    result = GenericScalar()


class Pause(Mutation):
    class Meta:
        description = sstrip('''
            Pause a workflow.
            This suspends submission of tasks.

            Valid for: running workflows.
        ''')
        resolver = mutator

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)

    result = GenericScalar()


class Message(Mutation):
    class Meta:
        description = sstrip('''
            Record task messages.

            Send messages to:
            - The job stdout/stderr.
            - The job status file, if there is one.
            - The scheduler, if communication is possible.

            Jobs use this to record and report status such
            as success and failure. Applications run by jobs can use
            this command to report messages and to report registered task
            outputs.

            Valid for: paused, running, stopping workflows.
        ''')
        resolver = partial(mutator, command='put_messages')

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)
        task_job = String(required=True)
        event_time = String(default_value=None)
        messages = graphene.List(
            graphene.List(String),
            description='List in the form `[[severity, message], ...]`.',
            default_value=None
        )

    result = GenericScalar()


class ReleaseHoldPoint(Mutation):
    class Meta:
        description = sstrip('''
            Release all tasks and unset the workflow hold point, if set.

            Held tasks do not submit their jobs even if ready to run.

            Valid for: paused, running workflows.
        ''')
        resolver = mutator

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)

    result = GenericScalar()


class Resume(Mutation):
    class Meta:
        description = sstrip('''
            Resume a paused workflow.

            See also the opposite command `pause`.

            Valid for: paused workflows.
        ''')
        resolver = mutator

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)

    result = GenericScalar()


class Reload(Mutation):
    class Meta:
        description = sstrip('''
            Reload the configuration of a running workflow.

            All settings including task definitions, with the exception of
            workflow log config, can be changed on reload. Changes to task
            definitions take effect immediately, unless a task is already
            running at reload time.

            If the workflow was started with Jinja2 template variables on the
            command line (cylc play --set "FOO='bar'" REG) the same template
            settings apply to the reload (only changes to the flow.cylc
            file itself are reloaded).

            If the modified workflow config does not parse, failure to reload
            will be reported but no harm will be done to the running workflow.

            Valid for: paused, running workflows.
        ''')
        resolver = partial(mutator, command='reload_workflow')

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)

    result = GenericScalar()


class SetVerbosity(Mutation):
    class Meta:
        description = sstrip('''
            Change the logging severity level of a running workflow.

            Only messages at or above the chosen severity level will be logged.
            For example, if you choose `WARNING`, only warning, error and
            critical level messages will be logged.

            Valid for: paused, running workflows.
        ''')
        resolver = mutator

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)
        level = LogLevels(required=True)

    result = GenericScalar()


class SetGraphWindowExtent(Mutation):
    class Meta:
        description = sstrip('''
            Set the maximum graph distance (n) from an active node
            of the data-store graph window.

            Valid for: paused, running workflows.
        ''')
        resolver = mutator

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)
        n_edge_distance = Int(required=True)

    result = GenericScalar()


class Stop(Mutation):
    class Meta:
        description = sstrip(f'''
            Tell a workflow to shut down or stop a specified
            flow from spawning any further.

            By default stopping workflows wait for submitted and running tasks
            to complete before shutting down. You can change this behaviour
            with the "mode" option.

            Tasks that become ready after the shutdown is ordered will be
            submitted immediately if the workflow is restarted.
            Remaining task event handlers, job poll and kill commands, will
            be executed prior to shutdown, unless
            the stop mode is `{WorkflowStopMode.Now.name}`.

            Valid for: paused, running, stopping workflows.
        ''')
        resolver = mutator

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)
        mode = WorkflowStopMode(
            default_value=WorkflowStopMode.Clean.name
        )
        cycle_point = CyclePoint(
            description='Stop after the workflow reaches this cycle.'
        )
        clock_time = TimePoint(
            description='Stop after wall-clock time passes this point.'
        )
        task = TaskID(
            description='Stop after this task succeeds.'
        )
        flow_num = Int(
            description='Number of flow to stop.'
        )

    result = GenericScalar()


class ExtTrigger(Mutation):
    class Meta:
        description = sstrip('''
            Report an external event message to a scheduler.

            External triggers allow any program to send
            messages to the Cylc scheduler. Cylc can use such
            messages as signals that an external prerequisite has
            been satisfied.

            The ID argument should be unique to each external
            trigger event. When an incoming message satisfies
            a task's external trigger the message ID is broadcast
            to all downstream tasks in the cycle point as
            `$CYLC_EXT_TRIGGER_ID`.  Tasks can use
            `$CYLC_EXT_TRIGGER_ID`, for example,  to
            identify a new data file that the external
            triggering system is responding to.

            Use the retry options in case the target workflow is down or out of
            contact.

            Note: To manually trigger a task use "Trigger" not
            "ExtTrigger".

            Valid for: paused, running workflows.
        ''')
        resolver = partial(mutator, command='put_ext_trigger')

    class Arguments:
        workflows = graphene.List(WorkflowID, required=True)
        message = String(
            description='External trigger message.',
            required=True
        )
        id = String(  # noqa: A003 (required for schema definition)
            description='Unique trigger ID.',
            required=True
        )

    result = GenericScalar()


class TaskMutation:
    class Arguments:
        workflows = graphene.List(
            WorkflowID,
            required=True
        )
        tasks = graphene.List(
            NamespaceIDGlob,
            required=True
        )

    result = GenericScalar()


class FlowMutationArguments:
    flow = graphene.List(
        graphene.NonNull(Flow),
        default_value=[],
        description=sstrip(f'''
            The flow(s) to trigger/set these tasks in.

            By default:
            * active tasks (n=0) keep their existing flow assignment
            * inactive tasks (n>0) get assigned all active flows

            Otherwise you can assign (inactive tasks) or add to (active tasks):
            * a list of integer flow numbers
            or one of the following strings:
            * {FLOW_ALL} - all active flows
            * {FLOW_NEW} - an automatically generated new flow number
            * {FLOW_NONE} - (ignored for active tasks): no flow
        ''')
    )
    flow_wait = Boolean(
        default_value=False,
        description=sstrip('''
            Should the workflow "wait" or "continue on" from this task?

            If `false` the scheduler will spawn and run downstream tasks
            as normal (default).

            If `true` the scheduler will not spawn the downstream tasks
            unless it has been caught by the same flow at a later time.

            For example you might set this to True to trigger a task
            ahead of a flow, where you don't want the scheduler to
            "continue on" from this task until the flow has caught up
            with it.
        ''')
    )
    flow_descr = String(
        description=sstrip('''
            If starting a new flow, this field can be used to provide the
            new flow with a description for later reference.
        ''')
    )


class Hold(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Hold tasks within a workflow.

            Held tasks do not submit their jobs even if ready to run.

            Valid for: paused, running workflows.
        ''')
        resolver = mutator


class Release(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Release held tasks within a workflow.

            See also the opposite command `hold`.

            Valid for: paused, running workflows.
        ''')
        resolver = mutator


class Kill(Mutation, TaskMutation):
    # TODO: This should be a job mutation?
    class Meta:
        description = sstrip('''
            Kill running or submitted jobs.

            Valid for: paused, running, stopping workflows.
        ''')
        resolver = partial(mutator, command='kill_tasks')


class Poll(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Poll (query) jobs to verify and update their statuses.

            This checks the job status file and queries the
            job runner on the job platform.

            Pollable tasks are those in the n=0 window with
            an associated job ID, including incomplete finished
            tasks.

            Valid for: paused, running, stopping workflows.
        ''')
        resolver = partial(mutator, command='poll_tasks')

    class Arguments(TaskMutation.Arguments):
        ...


class Remove(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Remove one or more task instances from a running workflow.

            Valid for: paused, running, stopping workflows.
        ''')
        resolver = partial(mutator, command='remove_tasks')

    class Arguments(TaskMutation.Arguments):
        flow = graphene.List(
            graphene.NonNull(Flow),
            default_value=[FLOW_ALL],
            description=sstrip(f'''
                "Remove the task(s) from the specified flows. "

                This should be a list of flow numbers, or '{FLOW_ALL}'
                to remove the task(s) from all flows they belong to
                (which is the default).
            ''')
        )


class SetPrereqsAndOutputs(Mutation, TaskMutation):
    class Meta:
        description = sstrip("""
            Set task prerequisites or outputs.

            By default, set all required outputs for target task(s).

            Setting prerequisites contributes to the task's readiness to run.

            Setting outputs contributes to the task's completion, sets the
            corresponding prerequisites of child tasks, and sets any implied
            outputs:
             - `started` implies `submitted`.
             - `succeeded` and `failed` imply `started`.
             - custom outputs and `expired` do not imply any other outputs.

            Valid for: paused, running, stopping workflows.
        """)
        resolver = partial(mutator, command='set')

    class Arguments(TaskMutation.Arguments, FlowMutationArguments):
        outputs = graphene.List(
            OutputLabel,
            description='List of task outputs to set complete.'
        )
        prerequisites = graphene.List(
            PrerequisiteString,
            description='List of task prerequisites to set satisfied.'
        )


class Trigger(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Manually trigger tasks, even in a paused workflow.

            Triggering an unqueued task queues it, to run when queue-released.
            Triggering a queued task runs it now regardless of queue limiting.

            The "on resume" option waits for a paused workflow to be resumed.

            Valid for: paused, running workflows.
        ''')
        resolver = partial(mutator, command='force_trigger_tasks')

    class Arguments(TaskMutation.Arguments, FlowMutationArguments):
        on_resume = Boolean(
            default_value=False,
            description=sstrip('''
                Run triggered tasks once the paused workflow is resumed.
            ''')
        )


def _mut_field(cls):
    """Convert a mutation class into a field.

    Sets the field metadata appropriately.

    Args:
        field (class):
            Subclass of graphene.Mutation

    Returns:
        graphene.Field

    """
    return cls.Field(description=cls._meta.description)


# Mutation declarations

class Mutations(ObjectType):
    # workflow actions
    broadcast = _mut_field(Broadcast)
    ext_trigger = _mut_field(ExtTrigger)
    message = _mut_field(Message)
    pause = _mut_field(Pause)
    reload = _mut_field(Reload)
    resume = _mut_field(Resume)
    set_verbosity = _mut_field(SetVerbosity)
    set_graph_window_extent = _mut_field(SetGraphWindowExtent)
    stop = _mut_field(Stop)
    set_hold_point = _mut_field(SetHoldPoint)
    release_hold_point = _mut_field(ReleaseHoldPoint)

    # task actions
    hold = _mut_field(Hold)
    kill = _mut_field(Kill)
    poll = _mut_field(Poll)
    release = _mut_field(Release)
    remove = _mut_field(Remove)
    set = _mut_field(SetPrereqsAndOutputs)  # noqa A003
    trigger = _mut_field(Trigger)

    # job actions
    # TODO


# ** Subscription Related ** #

# Used for the root entry points to yield the correct data
# from within the subscription async gen resolver.
SUB_RESOLVERS = {
    'workflows': get_workflows,
    'job': get_node_by_id,
    'jobs': get_nodes_all,
    'task': get_node_by_id,
    'tasks': get_nodes_all,
    'task_proxy': get_node_by_id,
    'task_proxies': get_nodes_all,
    'family': get_node_by_id,
    'families': get_nodes_all,
    'family_proxy': get_node_by_id,
    'family_proxies': get_nodes_all,
    'edges': get_edges_all,
    'nodes_edges': get_nodes_edges,
}


def delta_subs(root, info: 'ResolveInfo', **args) -> AsyncGenerator[Any, None]:
    """Generates the root data from the async gen resolver."""
    return get_resolvers(info).subscribe_delta(root, info, args)


class Pruned(ObjectType):
    class Meta:
        description = sstrip('''
            Objects (e.g. workflows, tasks, jobs) which have been removed from
            the store.
        ''')
    workflow = String()
    families = graphene.List(String, default_value=[])
    family_proxies = graphene.List(String, default_value=[])
    jobs = graphene.List(String, default_value=[])
    tasks = graphene.List(String, default_value=[])
    task_proxies = graphene.List(String, default_value=[])
    edges = graphene.List(String, default_value=[])


class Delta(Interface):
    """Interface for delta types.

    Since we usually subscribe to the same fields for both added/updated
    deltas this interface makes writing fragments easier.

    NOTE: This interface is specialised to the "added" type, other types must
    override fields as required.
    """

    families = graphene.List(
        Family,
        description='Family definitions.',
        args=DEF_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    family_proxies = graphene.List(
        FamilyProxy,
        description='Family cycle instances.',
        args=PROXY_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    jobs = graphene.List(
        Job,
        description='Jobs.',
        args=JOB_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    tasks = graphene.List(
        Task,
        description='Task definitions.',
        args=DEF_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    task_proxies = graphene.List(
        TaskProxy,
        description='Task cycle instances.',
        args=PROXY_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    edges = graphene.List(
        Edge,
        description='Graph edges',
        args=EDGE_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_edges_by_ids
    )
    workflow = Field(
        Workflow,
        description=Workflow._meta.description,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_workflow_by_id
    )


class Added(ObjectType):
    class Meta:
        description = 'Added node/edge deltas.'
        interfaces = (Delta,)


class Updated(ObjectType):
    class Meta:
        description = 'Updated node/edge deltas.'
        interfaces = (Delta,)

    families = graphene.List(
        Family,
        description='Family definitions.',
        args=DEF_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    family_proxies = graphene.List(
        FamilyProxy,
        description='Family cycle instances.',
        args=PROXY_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    jobs = graphene.List(
        Job,
        description='Jobs.',
        args=JOB_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    tasks = graphene.List(
        Task,
        description='Task definitions.',
        args=DEF_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    task_proxies = graphene.List(
        TaskProxy,
        description='Task cycle instances.',
        args=PROXY_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    edges = graphene.List(
        Edge,
        description='Graph edges.',
        args=EDGE_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_edges_by_ids
    )
    workflow = Field(
        Workflow,
        description=Workflow._meta.description,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_workflow_by_id
    )


class Deltas(ObjectType):
    class Meta:
        description = 'Grouped deltas of the WFS publish.'
    id = ID()  # noqa: A003 (required for schema definition)
    shutdown = Boolean(default_value=False)
    added = Field(
        Added,
        description=Added._meta.description,
        strip_null=Boolean(),
    )
    updated = Field(
        Updated,
        description=Updated._meta.description,
        strip_null=Boolean(),
    )
    pruned = Field(
        Pruned,
        description=Pruned._meta.description,
        strip_null=Boolean(),
    )


class Subscriptions(ObjectType):
    """Defines the subscriptions available in the schema."""
    class Meta:
        description = 'Multi-Workflow root level subscriptions.'

    deltas = Field(
        Deltas,
        description=Deltas._meta.description,
        workflows=graphene.List(
            ID, description="List of full ID, i.e. `~user/workflow_id`."
        ),
        strip_null=Boolean(default_value=False),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    workflows = graphene.List(
        Workflow,
        description=Workflow._meta.description,
        ids=graphene.List(ID, default_value=[]),
        exids=graphene.List(ID, default_value=[]),
        # TODO: Change these defaults post #3500 in coordination with WUI
        strip_null=Boolean(default_value=False),
        delta_store=Boolean(default_value=False),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=2.5),
        resolver=delta_subs
    )
    job = Field(
        Job,
        description=Job._meta.description,
        id=ID(required=True),
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    jobs = graphene.List(
        Job,
        description=Job._meta.description,
        args=ALL_JOB_ARGS,
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    task = Field(
        Task,
        description=Task._meta.description,
        id=ID(required=True),
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    tasks = graphene.List(
        Task,
        description=Task._meta.description,
        args=ALL_DEF_ARGS,
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    task_proxy = Field(
        TaskProxy,
        description=TaskProxy._meta.description,
        id=ID(required=True),
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    task_proxies = graphene.List(
        TaskProxy,
        description=TaskProxy._meta.description,
        args=ALL_PROXY_ARGS,
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    family = Field(
        Family,
        description=Family._meta.description,
        id=ID(required=True),
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    families = graphene.List(
        Family,
        description=Family._meta.description,
        args=ALL_DEF_ARGS,
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    family_proxy = Field(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        id=ID(required=True),
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    family_proxies = graphene.List(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        args=ALL_PROXY_ARGS,
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    edges = graphene.List(
        Edge,
        description=Edge._meta.description,
        args=ALL_EDGE_ARGS,
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    nodes_edges = Field(
        NodesEdges,
        description=NodesEdges._meta.description,
        args=NODES_EDGES_ARGS_ALL,
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )


schema = Schema(query=Queries, subscription=Subscriptions, mutation=Mutations)

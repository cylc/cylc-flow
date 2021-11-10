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
import logging
from operator import attrgetter
from textwrap import dedent
from typing import AsyncGenerator, Any

from graphene import (
    Boolean, Field, Float, ID, InputObjectType, Int,
    List, Mutation, ObjectType, Schema, String, Union, Enum,
    Argument, Interface
)
from graphene.types.generic import GenericScalar
from graphene.utils.str_converters import to_snake_case

from cylc.flow import ID_DELIM
from cylc.flow.broadcast_mgr import ALL_CYCLE_POINTS_STRS, addict
from cylc.flow.task_outputs import SORT_ORDERS
from cylc.flow.task_state import (
    TASK_OUTPUT_SUCCEEDED,
    TASK_STATUSES_ORDERED,
    TASK_STATUS_DESC,
    TASK_STATUS_WAITING,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED
)
from cylc.flow.data_store_mgr import (
    FAMILIES, FAMILY_PROXIES, JOBS, TASKS, TASK_PROXIES,
    DELTA_ADDED, DELTA_UPDATED
)
from cylc.flow.workflow_status import StopMode


def sstrip(text):
    """Simple function to dedent and strip text.

    Examples:
        >>> print(sstrip('''
        ...     foo
        ...       bar
        ...     baz
        ... '''))
        foo
          bar
        baz

    """
    return dedent(text).strip()


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


NODE_MAP = {
    'Task': TASKS,
    'TaskProxy': TASK_PROXIES,
    'Family': FAMILIES,
    'FamilyProxy': FAMILY_PROXIES,
    'Job': JOBS,
    'Node': PROXY_NODES,
}

CYCLING_TYPES = [
    'family_proxies',
    'family_proxy',
    'jobs',
    'job',
    'task_proxies',
    'task_proxy',
]

PROXY_TYPES = [
    'family_proxies',
    'family_proxy',
    'task_proxies',
    'task_proxy',
]

DEF_TYPES = [
    'families',
    'family',
    'tasks',
    'task',
]


def parse_workflow_id(item):
    """Split workflow id argument to individual workflow attributes.
    Args:
        item (owner|workflow:status):
            It's possible to traverse workflows,
            defaults to UI Server owner, and ``*`` glob for workflow.

    Returns:
        A tuple of id components in respective order. For example:

        (owner, name, status)
    """
    owner, workflow, status = (None, None, None)
    if ':' in item:
        head, status = item.rsplit(':', 1)
    else:
        head, status = (item, None)
    if head.count(ID_DELIM):
        owner, workflow = head.split(ID_DELIM, 1)
    else:
        # more common to filter on workflow (with owner constant)
        workflow = head
    return (owner, workflow, status)


def parse_node_id(item, node_type=None):
    """Parse definition, job, or proxy id argument returning components.

    Args:
        item (str): A string representing a node ID. Jobs fill out
            cycle|name|num first, cycle is irrelevant to Def
            owner|workflow is always last.
            For example:

            name
            cycle|na*
            workflow|cycle|name
            owner|workflow|cycle|name|submit_num:state
            cycle|*|submit_num
        node_type (str):
            the type of the node to be parsed.

    Returns:
        A tuple of string id components in respective order. For example:

        (owner, workflow, cycle, name, submit_num, state)

        None type is set for missing components.
    """
    if ':' in item:
        head, state = item.rsplit(':', 1)
    else:
        head, state = (item, None)
    if ID_DELIM in head:
        dil_count = head.count(ID_DELIM)
        parts = head.split(ID_DELIM, dil_count)
    else:
        return (None, None, None, head, None, state)
    if node_type in DEF_TYPES:
        owner, workflow, name = [None] * (2 - dil_count) + parts
        parts = [owner, workflow, None, name, None]
    elif node_type in PROXY_TYPES:
        parts = [None] * (3 - dil_count) + parts + [None]
    elif dil_count < 4:
        if dil_count < 3:
            parts = [None, None] + parts + [None] * (2 - dil_count)
        else:
            parts = [None] * (4 - dil_count) + parts
    parts += [state]
    return tuple(parts)


# ** Query Related **#

# Field args (i.e. for queries etc):
class SortArgs(InputObjectType):
    keys = List(String, default_value=['id'])
    reverse = Boolean(default_value=False)


GHOSTS_DEFAULT = Boolean(default_value=False)
STRIP_NULL_DEFAULT = Argument(
    Boolean, description="A flag that when enabled strips out those fields "
                         "not set in the protobuf object. And when this flag "
                         "is disabled the default values of Protobuf fields "
                         "are provided (boolean=false, list=[], string=\"\".")
DELTA_STORE_DEFAULT = Boolean(default_value=False)
DELTA_TYPE_DEFAULT = String(default_value='added')

JOB_ARGS = {
    'ids': List(ID, default_value=[]),
    'exids': List(ID, default_value=[]),
    'states': List(String, default_value=[]),
    'exstates': List(String, default_value=[]),
    'sort': SortArgs(default_value=None),
}

ALL_JOB_ARGS = {
    'workflows': List(ID, default_value=[]),
    'exworkflows': List(ID, default_value=[]),
    'ids': List(ID, default_value=[]),
    'exids': List(ID, default_value=[]),
    'states': List(String, default_value=[]),
    'exstates': List(String, default_value=[]),
    'sort': SortArgs(default_value=None),
}

DEF_ARGS = {
    'ids': List(ID, default_value=[]),
    'exids': List(ID, default_value=[]),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

ALL_DEF_ARGS = {
    'workflows': List(ID, default_value=[]),
    'exworkflows': List(ID, default_value=[]),
    'ids': List(ID, default_value=[]),
    'exids': List(ID, default_value=[]),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

PROXY_ARGS = {
    'ids': List(ID, default_value=[]),
    'exids': List(ID, default_value=[]),
    'states': List(String, default_value=[]),
    'exstates': List(String, default_value=[]),
    'is_held': Boolean(),
    'is_queued': Boolean(),
    'is_runahead': Boolean(),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

ALL_PROXY_ARGS = {
    'workflows': List(ID, default_value=[]),
    'exworkflows': List(ID, default_value=[]),
    'ids': List(ID, default_value=[]),
    'exids': List(ID, default_value=[]),
    'states': List(String, default_value=[]),
    'exstates': List(String, default_value=[]),
    'is_held': Boolean(),
    'is_queued': Boolean(),
    'is_runahead': Boolean(),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

EDGE_ARGS = {
    'ids': List(ID, default_value=[]),
    'exids': List(ID, default_value=[]),
    'states': List(String, default_value=[]),
    'exstates': List(String, default_value=[]),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

ALL_EDGE_ARGS = {
    'workflows': List(ID, default_value=[]),
    'exworkflows': List(ID, default_value=[]),
    'sort': SortArgs(default_value=None),
}

NODES_EDGES_ARGS = {
    'ids': List(ID, default_value=[]),
    'exids': List(ID, default_value=[]),
    'states': List(String, default_value=[]),
    'exstates': List(String, default_value=[]),
    'is_held': Boolean(),
    'is_queued': Boolean(),
    'is_runahead': Boolean(),
    'distance': Int(default_value=1),
    'mindepth': Int(default_value=-1),
    'maxdepth': Int(default_value=-1),
    'sort': SortArgs(default_value=None),
}

NODES_EDGES_ARGS_ALL = {
    'workflows': List(ID, default_value=[]),
    'exworkflows': List(ID, default_value=[]),
    'ids': List(ID, default_value=[]),
    'exids': List(ID, default_value=[]),
    'states': List(String, default_value=[]),
    'exstates': List(String, default_value=[]),
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

def get_type_str(obj_type):
    """Iterate through the objects of_type to find the inner-most type."""
    pointer = obj_type
    while hasattr(pointer, 'of_type'):
        pointer = pointer.of_type
    return str(pointer).replace('!', '')


def process_resolver_info(root, info, args):
    """Set and gather info for resolver."""
    # Add the subscription id to the resolver context
    # to know which delta-store to use."""
    if 'backend_sub_id' in info.variable_values:
        args['sub_id'] = info.variable_values['backend_sub_id']

    field_name = to_snake_case(info.field_name)
    # root is the parent data object.
    # i.e. PbWorkflow or list of IDs List(String)
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


async def get_workflows(root, info, **args):
    """Get filtered workflows."""

    _, workflow = process_resolver_info(root, info, args)
    if workflow is not None:
        args['ids'] = [workflow.id]

    args['workflows'] = [parse_workflow_id(w_id) for w_id in args['ids']]
    args['exworkflows'] = [parse_workflow_id(w_id) for w_id in args['exids']]
    resolvers = info.context.get('resolvers')
    return await resolvers.get_workflows(args)


async def get_workflow_by_id(root, info, **args):
    """Return single workflow element."""

    _, workflow = process_resolver_info(root, info, args)
    if workflow is not None:
        args['id'] = workflow.id

    args['workflow'] = args['id']
    resolvers = info.context.get('resolvers')
    return await resolvers.get_workflow_by_id(args)


async def get_nodes_all(root, info, **args):
    """Resolver for returning job, task, family nodes"""

    _, field_ids = process_resolver_info(root, info, args)

    if hasattr(args, 'id'):
        args['ids'] = [args.get('id')]
    if field_ids:
        if isinstance(field_ids, str):
            field_ids = [field_ids]
        elif isinstance(field_ids, dict):
            field_ids = list(field_ids)
        args['ids'] = field_ids
    elif field_ids == []:
        return []

    node_type = NODE_MAP[get_type_str(info.return_type)]

    args['ids'] = [parse_node_id(n_id, node_type) for n_id in args['ids']]
    args['exids'] = [parse_node_id(n_id, node_type) for n_id in args['exids']]
    args['workflows'] = [
        parse_workflow_id(w_id) for w_id in args['workflows']]
    args['exworkflows'] = [
        parse_workflow_id(w_id) for w_id in args['exworkflows']]
    resolvers = info.context.get('resolvers')
    return await resolvers.get_nodes_all(node_type, args)


async def get_nodes_by_ids(root, info, **args):
    """Resolver for returning job, task, family node"""

    field_name, field_ids = process_resolver_info(root, info, args)

    resolvers = info.context.get('resolvers')
    if field_ids == []:
        parent_id = getattr(root, 'id', None)
        # Find node ids from parent
        if parent_id:
            parent_args = deepcopy(args)
            parent_args.update(
                {'id': parent_id, 'delta_store': False}
            )
            parent_type = get_type_str(info.parent_type)
            if parent_type in NODE_MAP:
                parent = await resolvers.get_node_by_id(
                    NODE_MAP[parent_type], parent_args)
            else:
                parent = await resolvers.get_workflow_by_id(parent_args)
            field_ids = getattr(parent, field_name, None)
        if not field_ids:
            return []
    if field_ids:
        args['native_ids'] = get_native_ids(field_ids)

    node_type = NODE_MAP[get_type_str(info.return_type)]

    args['ids'] = [parse_node_id(n_id, node_type) for n_id in args['ids']]
    args['exids'] = [parse_node_id(n_id, node_type) for n_id in args['exids']]
    return await resolvers.get_nodes_by_ids(node_type, args)


async def get_node_by_id(root, info, **args):
    """Resolver for returning job, task, family node"""

    field_name, field_id = process_resolver_info(root, info, args)

    if field_name == 'source_node':
        field_name = 'source'
    elif field_name == 'target_node':
        field_name = 'target'

    resolvers = info.context.get('resolvers')
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
                    NODE_MAP[get_type_str(info.parent_type)],
                    parent_args
                )
                field_id = getattr(parent, field_name, None)
        if field_id:
            args['id'] = field_id
        else:
            return None

    return await resolvers.get_node_by_id(
        NODE_MAP[get_type_str(info.return_type)],
        args)


async def get_edges_all(root, info, **args):
    """Get all edges from the store filtered by args."""

    process_resolver_info(root, info, args)

    args['workflows'] = [
        parse_workflow_id(w_id) for w_id in args['workflows']]
    args['exworkflows'] = [
        parse_workflow_id(w_id) for w_id in args['exworkflows']]
    resolvers = info.context.get('resolvers')
    return await resolvers.get_edges_all(args)


async def get_edges_by_ids(root, info, **args):
    """Get all edges from the store by id lookup filtered by args."""

    _, field_ids = process_resolver_info(root, info, args)

    if field_ids:
        args['native_ids'] = get_native_ids(field_ids)
    elif field_ids == []:
        return []

    resolvers = info.context.get('resolvers')
    return await resolvers.get_edges_by_ids(args)


async def get_nodes_edges(root, info, **args):
    """Resolver for returning job, task, family nodes"""

    process_resolver_info(root, info, args)

    if hasattr(root, 'id'):
        args['workflows'] = [parse_workflow_id(root.id)]
        args['exworkflows'] = []
    else:
        args['workflows'] = [
            parse_workflow_id(w_id) for w_id in args['workflows']]
        args['exworkflows'] = [
            parse_workflow_id(w_id) for w_id in args['exworkflows']]

    node_type = NODE_MAP['TaskProxy']
    args['ids'] = [parse_node_id(n_id, node_type) for n_id in args['ids']]
    args['exids'] = [parse_node_id(n_id, node_type) for n_id in args['exids']]

    resolvers = info.context.get('resolvers')
    root_nodes = await resolvers.get_nodes_all(node_type, args)
    return await resolvers.get_nodes_edges(root_nodes, args)


def resolve_state_totals(root, info, **args):
    state_totals = {state: 0 for state in TASK_STATUSES_ORDERED}
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


async def resolve_broadcasts(root, info, **args):
    """Resolve and parse broadcasts from JSON."""
    broadcasts = json.loads(
        getattr(root, to_snake_case(info.field_name), '{}'))
    resolvers = info.context.get('resolvers')

    if not args['ids']:
        return broadcasts

    result = {}
    t_type = NODE_MAP['Task']
    t_args = {'workflows': [parse_workflow_id(root.id)]}
    tp_type = NODE_MAP['TaskProxy']
    for n_id in args['ids']:
        _, _, point_string, name, _, _ = parse_node_id(n_id, tp_type)
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
        description = """
Meta data fields,
including custom fields in a generic user-defined dump"""
    title = String(default_value=None)
    description = String(default_value=None)
    URL = String(default_value=None)
    user_defined = GenericScalar(resolver=resolve_json_dump)


class TimeZone(ObjectType):
    class Meta:
        description = """Time zone info."""
    hours = Int()
    minutes = Int()
    string_basic = String()
    string_extended = String()


class Workflow(ObjectType):
    class Meta:
        description = """Global workflow info."""
    id = ID()  # noqa: A003 (required for definition)
    name = String()
    status = String()
    status_msg = String()
    host = String()
    port = Int()
    pub_port = Int()
    owner = String()
    tasks = List(
        lambda: Task,
        description="""Task definitions.""",
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    families = List(
        lambda: Family,
        description="""Family definitions.""",
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    task_proxies = List(
        lambda: TaskProxy,
        description="""Task cycle instances.""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    family_proxies = List(
        lambda: FamilyProxy,
        description="""Family cycle instances.""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    jobs = List(
        lambda: Job,
        description="""Task jobs.""",
        args=JOB_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    edges = Field(
        lambda: Edges,
        args=EDGE_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        description="""Graph edges""")
    nodes_edges = Field(
        lambda: NodesEdges,
        args=NODES_EDGES_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_edges)
    api_version = Int()
    cylc_version = String()
    last_updated = Float()
    meta = Field(NodeMeta)
    newest_active_cycle_point = String()
    oldest_active_cycle_point = String()
    reloaded = Boolean()
    run_mode = String()
    is_held_total = Int()
    is_queued_total = Int()
    is_runahead_total = Int()
    state_totals = GenericScalar(resolver=resolve_state_totals)
    latest_state_tasks = GenericScalar(
        states=List(
            String,
            description="List of task states to show",
            default_value=TASK_STATUSES_ORDERED),
        resolver=resolve_state_tasks)
    workflow_log_dir = String()
    time_zone_info = Field(TimeZone)
    tree_depth = Int()
    ns_def_order = List(String)
    job_log_names = List(String)
    states = List(String)
    broadcasts = GenericScalar(
        ids=List(
            ID,
            description=sstrip('''
                Node IDs, cycle point and/or-just family/task namespace:
                    ["foo.1234", "1234|foo", "FAM.1234", "FAM.*"]
            '''),
            default_value=[]),
        resolver=resolve_broadcasts)
    pruned = Boolean()


class Job(ObjectType):
    class Meta:
        description = """Jobs."""
    id = ID()  # noqa: A003 (required for definition)
    submit_num = Int()
    state = String()
    # name and cycle_point for filtering/sorting
    name = String()
    cycle_point = String()
    task_proxy = Field(
        lambda: TaskProxy,
        description="""Associated Task Proxy""",
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    submitted_time = String()
    started_time = String()
    finished_time = String()
    job_id = ID()
    job_runner_name = String()
    env_script = String()
    err_script = String()
    exit_script = String()
    execution_time_limit = Float()
    platform = String()
    init_script = String()
    job_log_dir = String()
    post_script = String()
    pre_script = String()
    script = String()
    work_sub_dir = String()
    environment = GenericScalar(resolver=resolve_json_dump)
    directives = GenericScalar(resolver=resolve_json_dump)
    param_var = GenericScalar(resolver=resolve_json_dump)
    extra_logs = List(String)
    messages = List(String)


class Task(ObjectType):
    class Meta:
        description = """Task definition, static fields"""
    id = ID()  # noqa: A003 (required for definition)
    name = String()
    meta = Field(NodeMeta)
    mean_elapsed_time = Float()
    depth = Int()
    proxies = List(
        lambda: TaskProxy,
        description="""Associated cycle point proxies""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    parents = List(
        lambda: Family,
        description="""Family definition parent.""",
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    namespace = List(String)
    first_parent = Field(
        lambda: Family,
        description="""Task first parent.""",
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)


class PollTask(ObjectType):
    class Meta:
        description = """Polling task edge"""
    local_proxy = ID()
    workflow = String()
    remote_proxy = ID()
    req_state = String()
    graph_string = String()


class Condition(ObjectType):
    class Meta:
        description = """Prerequisite conditions."""
    task_id = String()
    task_proxy = Field(
        lambda: TaskProxy,
        description="""Associated Task Proxy""",
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
        description = """Task prerequisite."""
    expression = String()
    conditions = List(
        Condition,
        description="""Condition monomers of a task prerequisites.""")
    cycle_points = List(String)
    satisfied = Boolean()


class Output(ObjectType):
    class Meta:
        description = """Task output"""
    label = String()
    message = String()
    satisfied = Boolean()
    time = Float()


class ClockTrigger(ObjectType):
    class Meta:
        description = """Task clock-trigger"""
    time = Float()
    time_string = String()
    satisfied = Boolean()


class XTrigger(ObjectType):
    class Meta:
        description = """Task trigger"""
    id = String()  # noqa: A003 (required for definition)
    label = String()
    message = String()
    satisfied = Boolean()
    time = Float()


class TaskProxy(ObjectType):
    class Meta:
        description = """Task cycle instance."""
    id = ID()  # noqa: A003 (required for schema definition)
    task = Field(
        Task,
        description="""Task definition""",
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    state = String()
    cycle_point = String()
    is_held = Boolean()
    is_queued = Boolean()
    is_runahead = Boolean()
    flow_nums = String()
    depth = Int()
    job_submits = Int()
    outputs = List(
        Output,
        description="""Task outputs.""",
        sort=SortArgs(default_value=None),
        sort_order=List(
            String,
            default_value=list(SORT_ORDERS)
        ),
        limit=Int(default_value=0),
        satisfied=Boolean(),
        resolver=resolve_mapping_to_list)
    clock_trigger = Field(ClockTrigger)
    external_triggers = List(
        XTrigger,
        description="""Task external trigger prerequisites.""",
        sort=SortArgs(default_value=None),
        sort_order=List(String),
        limit=Int(default_value=0),
        satisfied=Boolean(),
        resolver=resolve_mapping_to_list)
    xtriggers = List(
        XTrigger,
        description="""Task xtrigger prerequisites.""",
        sort=SortArgs(default_value=None),
        sort_order=List(String),
        limit=Int(default_value=0),
        satisfied=Boolean(),
        resolver=resolve_mapping_to_list)
    extras = GenericScalar(resolver=resolve_json_dump)
    # name & namespace for filtering/sorting
    name = String()
    namespace = List(String)
    prerequisites = List(Prerequisite)
    jobs = List(
        Job,
        description="""Task jobs.""",
        args=JOB_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    parents = List(
        lambda: FamilyProxy,
        description="""Task parents.""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    first_parent = Field(
        lambda: FamilyProxy,
        description="""Task first parent.""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    ancestors = List(
        lambda: FamilyProxy,
        description="""First parent ancestors.""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)


class Family(ObjectType):
    class Meta:
        description = """Task definition, static fields"""
    id = ID()  # noqa: A003 (required for schema definition)
    name = String()
    meta = Field(NodeMeta)
    depth = Int()
    proxies = List(
        lambda: FamilyProxy,
        description="""Associated cycle point proxies""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    parents = List(
        lambda: Family,
        description="""Family definition parent.""",
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    child_tasks = List(
        Task,
        description="""Descendant definition tasks.""",
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    child_families = List(
        lambda: Family,
        description="""Descendant desc families.""",
        args=DEF_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    first_parent = Field(
        lambda: Family,
        description="""Family first parent.""",
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)


class FamilyProxy(ObjectType):
    class Meta:
        description = """Family composite."""
    id = ID()  # noqa: A003 (required for schema definition)
    cycle_point = String()
    # name & namespace for filtering/sorting
    name = String()
    family = Field(
        Family,
        description="""Family definition""",
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    state = String()
    states = List(String)
    state_totals = GenericScalar(resolver=resolve_state_totals)
    is_held = Boolean()
    is_held_total = Int()
    is_queued = Boolean()
    is_queued_total = Int()
    is_runahead = Boolean()
    is_runahead_total = Int()
    depth = Int()
    child_tasks = List(
        TaskProxy,
        description="""Descendant task proxies.""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    child_families = List(
        lambda: FamilyProxy,
        description="""Descendant family proxies.""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)
    first_parent = Field(
        lambda: FamilyProxy,
        description="""Task first parent.""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_node_by_id)
    ancestors = List(
        lambda: FamilyProxy,
        description="""First parent ancestors.""",
        args=PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_nodes_by_ids)


class Node(Union):
    class Meta:
        types = (TaskProxy, FamilyProxy)

    @classmethod
    def resolve_type(cls, instance, info):
        if hasattr(instance, 'task'):
            return TaskProxy
        return FamilyProxy


class Edge(ObjectType):
    class Meta:
        description = """Dependency edge task/family proxies"""
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
        description = """Dependency edge"""
    edges = List(
        Edge,
        args=EDGE_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        delta_store=DELTA_STORE_DEFAULT,
        delta_type=DELTA_TYPE_DEFAULT,
        resolver=get_edges_by_ids)
    workflow_polling_tasks = List(PollTask)
    leaves = List(String)
    feet = List(String)


class NodesEdges(ObjectType):
    class Meta:
        description = """Related Nodes & Edges."""
    nodes = List(
        TaskProxy,
        description="""Task nodes from and including root.""")
    edges = List(
        Edge,
        description="""Edges associated with the nodes.""")


# Query declaration
class Queries(ObjectType):
    class Meta:
        description = """Multi-Workflow root level queries."""
    workflows = List(
        Workflow,
        description=Workflow._meta.description,
        ids=List(ID, default_value=[]),
        exids=List(ID, default_value=[]),
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_workflows)
    job = Field(
        Job,
        description=Job._meta.description,
        id=ID(required=True),
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_node_by_id)
    jobs = List(
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
    tasks = List(
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
    task_proxies = List(
        TaskProxy,
        description=TaskProxy._meta.description,
        args=ALL_PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_nodes_all)
    family = Field(
        Family,
        description=Family._meta.description,
        id=ID(required=True),
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_node_by_id)
    families = List(
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
    family_proxies = List(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        args=ALL_PROXY_ARGS,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_nodes_all)
    edges = List(
        Edge,
        description=Edge._meta.description,
        args=ALL_EDGE_ARGS,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_edges_all)
    nodes_edges = Field(
        NodesEdges,
        description=NodesEdges._meta.description,
        args=NODES_EDGES_ARGS_ALL,
        ghosts=GHOSTS_DEFAULT,
        strip_null=STRIP_NULL_DEFAULT,
        resolver=get_nodes_edges)


# ** Mutation Related ** #


# Generic containers
class GenericResponse(ObjectType):
    class Meta:
        description = """Container for command queued response"""

    result = GenericScalar()


# Mutators are used to call the internals of the parent program in the
# resolution of mutation requests (or can make external calls themselves).
# Like query resolvers (read above), they are treated as implicit
# static methods, with object context pass in as the first argument.

# Mutators:

async def mutator(root, info, command=None, workflows=None,
                  exworkflows=None, **args):
    """Call the resolver method that act on the workflow service
    via the internal command queue."""
    if workflows is None:
        workflows = []
    if exworkflows is None:
        exworkflows = []
    w_args = {}
    w_args['workflows'] = [parse_workflow_id(w_id) for w_id in workflows]
    w_args['exworkflows'] = [parse_workflow_id(w_id) for w_id in exworkflows]
    if args.get('args', False):
        args.update(args.get('args', {}))
        args.pop('args')
    resolvers = info.context.get('resolvers')
    res = await resolvers.mutator(info, command, w_args, args)
    return GenericResponse(result=res)


async def nodes_mutator(root, info, command, ids, workflows=None,
                        exworkflows=None, **args):
    """Call the resolver method, dealing with multiple node id arguments,
    which acts on the workflow service via the internal command queue."""
    if command == 'put_messages':
        node_type = 'jobs'
    else:
        node_type = 'task_proxy'
    ids = [parse_node_id(n_id, node_type) for n_id in ids]
    # if the workflows arg is empty extract from proxy args
    if workflows is None:
        workflows = set()
        for owner, workflow, _, _, _, _ in ids:
            if owner and workflow:
                workflows.add(f'{owner}{ID_DELIM}{workflow}')
            elif workflow:
                workflows.add(workflow)
    if not workflows:
        return GenericResponse(result="Error: No given Workflow(s)")
    if exworkflows is None:
        exworkflows = []
    w_args = {}
    w_args['workflows'] = [parse_workflow_id(w_id) for w_id in workflows]
    w_args['exworkflows'] = [parse_workflow_id(w_id) for w_id in exworkflows]
    if args.get('args', False):
        args.update(args.get('args', {}))
        args.pop('args')
    resolvers = info.context.get('resolvers')
    res = await resolvers.nodes_mutator(info, command, ids, w_args, args)
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


class BroadcastMode(Enum):
    Set = 'put_broadcast'
    Clear = 'clear_broadcast'
    Expire = 'expire_broadcast'

    @property
    def description(self):
        if self == BroadcastMode.Set:
            return 'Create a new broadcast.'
        if self == BroadcastMode.Clear:
            return 'Revoke an existing broadcast.'
        if self == BroadcastMode.Expire:
            return 'Expire an existing broadcast.'
        return ''


class BroadcastSetting(GenericScalar):
    """A [runtime] key=value configuration for a namespace.

    Should be a key=value pair where sections are wrapped with square
    brackets.

    Examples:
        script=true
        [environment]ANSWER=42

    Nested sections should only have one set of square brackets e.g:

        [section][subsection][subsubsection]=value

    """


class TaskStatus(Enum):
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
        If a task is held no new job submissions will be made
    '''))
    is_queued = Boolean(description=sstrip('''
        Task is queued for job submission
    '''))
    is_runahead = Boolean(description=sstrip('''
        Task is runahead limited
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


LogLevels = Enum(
    'LogLevels',
    list(logging._nameToLevel.items()),
    description=lambda x: f'Python logging level: {x.name} = {x.value}.'
    if x else ''
)


class WorkflowStopMode(Enum):
    """The mode used to stop a running workflow."""

    # NOTE: using a different enum because:
    # * Graphene requires special enums.
    # * We only want to offer a subset of stop modes (REQUEST_* only).

    Clean = StopMode.REQUEST_CLEAN.value  # type: Enum
    Kill = StopMode.REQUEST_KILL.value  # type: Enum
    Now = StopMode.REQUEST_NOW.value  # type: Enum
    NowNow = StopMode.REQUEST_NOW_NOW.value  # type: Enum

    @property
    def description(self):
        return StopMode(self.value).describe()


# Mutations:

# TODO: re-instate:
# - get-broadcast (can just use GraphQL query BUT needs CLI access too)
# - expire-broadcast

class Broadcast(Mutation):
    class Meta:
        description = sstrip('''
            Override or add new `[runtime]` configurations in a running
            workflow.

            Uses for broadcast include making temporary changes to task
            behaviour, and task-to-downstream-task communication via
            environment variables.

            A broadcast can target any [runtime] namespace for all cycles or
            for a specific cycle. If a task is affected by specific-cycle and
            all-cycle broadcasts at once, the specific takes precedence. If
            a task is affected by broadcasts to multiple ancestor
            namespaces, the result is determined by normal [runtime]
            inheritance. In other words, it follows this order:

            `all:root -> all:FAM -> all:task -> tag:root -> tag:FAM ->
            tag:task`

            Broadcasts persist, even across restarts, until they expire
            when their target cycle point is older than the oldest current in
            the workflow, or until they are explicitly cancelled with this
            command.  All-cycle broadcasts do not expire.

            For each task the final effect of all broadcasts to all namespaces
            is computed on the fly just prior to job submission.  The
            `--cancel` and `--clear` options simply cancel (remove) active
            broadcasts, they do not act directly on the final task-level
            result. Consequently, for example, you cannot broadcast to "all
            cycles except Tn" with an all-cycle broadcast followed by a cancel
            to Tn (there is no direct broadcast to Tn to cancel); and you
            cannot broadcast to "all members of FAMILY except member_n" with a
            general broadcast to FAMILY followed by a cancel to member_n (there
            is no direct broadcast to member_n to cancel).
        ''')
        resolver = partial(mutator, command='broadcast')

    class Arguments:
        workflows = List(WorkflowID, required=True)

        mode = BroadcastMode(
            # use the enum name as the default value
            # https://github.com/graphql-python/graphql-core-legacy/issues/166
            default_value=BroadcastMode.Set.name,  # type: ignore
            description='What type of broadcast is this?',
            required=True
        )
        cycle_points = List(
            CyclePoint,
            description=sstrip('''
                List of cycle points to target or `*` to cancel all all-cycle
                broadcasts without canceling all specific-cycle broadcasts.
            '''),
            default_value=['*'])
        namespaces = List(
            NamespaceName,
            description='Target namespaces.',
            default_value=['root']
        )
        settings = List(
            BroadcastSetting,
            description=sstrip('''
                The cylc namespace for the setting to modify.
            '''),
            # e.g. `{environment: {variable_name: "value",. . .}. . .}`.
        )
        cutoff = CyclePoint(
            description='Clear broadcasts earlier than cutoff cycle point.'
        )

        # TODO: work out how to implement this feature, it needs to be
        #       handled client-side which makes it slightly awkward in
        #       api-on-the-fly land

        # files = List(
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
        ''')
        resolver = partial(mutator, command='set_hold_point')

    class Arguments:
        workflows = List(WorkflowID, required=True)
        point = CyclePoint(
            description='Hold all tasks after the specified cycle point.',
            required=True
        )

    result = GenericScalar()


class Pause(Mutation):
    class Meta:
        description = sstrip('''
            Pause a workflow.

            This prevents submission of any task jobs.
        ''')
        resolver = partial(mutator, command='pause')

    class Arguments:
        workflows = List(WorkflowID, required=True)

    result = GenericScalar()


class Message(Mutation):
    class Meta:
        description = sstrip('''
            Record task job messages.

            Send task job messages to:
            - The job stdout/stderr.
            - The job status file, if there is one.
            - The scheduler, if communication is possible.

            Task jobs use this to record and report status such
            as success and failure. Applications run by task jobs can use
            this command to report messages and to report registered task
            outputs.
        ''')
        resolver = partial(mutator, command='put_messages')

    class Arguments:
        workflows = List(WorkflowID, required=True)
        task_job = String(required=True)
        event_time = String(default_value=None)
        messages = List(
            List(String),
            description="""List in the form `[[severity, message], ...]`.""",
            default_value=None
        )

    result = GenericScalar()


class ReleaseHoldPoint(Mutation):
    class Meta:
        description = sstrip('''
            Release all tasks and unset the workflow hold point, if set.

            Held tasks do not submit their jobs even if ready to run.
        ''')
        resolver = partial(mutator, command='release_hold_point')

    class Arguments:
        workflows = List(WorkflowID, required=True)

    result = GenericScalar()


class Resume(Mutation):
    class Meta:
        description = sstrip('''
            Resume a paused workflow.

            See also the opposite command `pause`.
        ''')
        resolver = partial(mutator, command='resume')

    class Arguments:
        workflows = List(WorkflowID, required=True)

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
        ''')
        resolver = partial(mutator, command='reload_workflow')

    class Arguments:
        workflows = List(WorkflowID, required=True)

    result = GenericScalar()


class SetVerbosity(Mutation):
    class Meta:
        description = sstrip('''
            Change the logging severity level of a running workflow.

            Only messages at or above the chosen severity level will be logged;
            for example, if you choose `WARNING`, only warnings and critical
            messages will be logged.
        ''')
        resolver = partial(mutator, command='set_verbosity')

    class Arguments:
        workflows = List(WorkflowID, required=True)
        level = LogLevels(required=True)

    result = GenericScalar()


class SetGraphWindowExtent(Mutation):
    class Meta:
        description = sstrip('''
            Set the maximum graph distance (n) from an active node
            of the data-store graph window.

        ''')
        resolver = partial(mutator, command='set_graph_window_extent')

    class Arguments:
        workflows = List(WorkflowID, required=True)
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
        ''')
        resolver = partial(mutator, command='stop')

    class Arguments:
        workflows = List(WorkflowID, required=True)
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
            ``$CYLC_EXT_TRIGGER_ID``.  Tasks can use
            ``$CYLC_EXT_TRIGGER_ID``, for example,  to
            identify a new data file that the external
            triggering system is responding to.

            Use the retry options in case the target workflow is down or out of
            contact.

            Note: To manually trigger a task use "Trigger" not
            "ExtTrigger".
        ''')
        resolver = partial(mutator, command='put_ext_trigger')

    class Arguments:
        workflows = List(WorkflowID, required=True)
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
        workflows = List(
            WorkflowID,
            required=True
        )
        tasks = List(
            NamespaceIDGlob,
            required=True
        )

    result = GenericScalar()


class Hold(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Hold tasks within a workflow.

            Held tasks do not submit their jobs even if ready to run.
        ''')
        resolver = partial(mutator, command='hold')


class Release(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Release held tasks within a workflow.

            See also the opposite command `hold`.
        ''')
        resolver = partial(mutator, command='release')


class Kill(Mutation, TaskMutation):
    # TODO: This should be a job mutation?
    class Meta:
        description = sstrip('''
            Kill running or submitted jobs.
        ''')
        resolver = partial(mutator, command='kill_tasks')


class Poll(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Poll (query) task jobs to verify and update their statuses.

            This checks the job status file and queries the
            job runner on the job platform.

            Pollable tasks are those in the n=0 window with
            an associated job ID, including incomplete finished
            tasks.
        ''')
        resolver = partial(mutator, command='poll_tasks')

    class Arguments(TaskMutation.Arguments):
        ...


class Remove(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Remove one or more task instances from a running workflow.

        ''')
        resolver = partial(mutator, command='remove_tasks')


class SetOutputs(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Artificially mark task outputs as completed.

            This allows you to manually intervene with Cylc's scheduling
            algorithm by artificially satisfying outputs of tasks.

            By default this makes tasks appear as if they succeeded.
        ''')
        resolver = partial(mutator, command='force_spawn_children')

    class Arguments(TaskMutation.Arguments):
        outputs = List(
            String,
            default_value=[TASK_OUTPUT_SUCCEEDED],
            description='List of task outputs to satisfy.'
        )
        flow_num = Int()


class Trigger(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Manually trigger tasks.

            Warning: waiting tasks that are queue-limited will be queued if
            triggered, to submit as normal when released by the queue; queued
            tasks will submit immediately if triggered, even if that violates
            the queue limit (so you may need to trigger a queue-limited task
            twice to get it to submit immediately).
        ''')
        resolver = partial(mutator, command='force_trigger_tasks')

    class Arguments(TaskMutation.Arguments):
        reflow = Boolean()
        flow_descr = String()


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
    set_outputs = _mut_field(SetOutputs)
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


def delta_subs(root, info, **args) -> AsyncGenerator[Any, None]:
    """Generates the root data from the async gen resolver."""
    return info.context.get('resolvers').subscribe_delta(root, info, args)


class Pruned(ObjectType):
    class Meta:
        description = """WFS Nodes/Edges that have been removed."""
    workflow = String()
    families = List(String, default_value=[])
    family_proxies = List(String, default_value=[])
    jobs = List(String, default_value=[])
    tasks = List(String, default_value=[])
    task_proxies = List(String, default_value=[])
    edges = List(String, default_value=[])


class Delta(Interface):
    """Interface for delta types.

    Since we usually subscribe to the same fields for both added/updated
    deltas this interface makes writing fragments easier.

    NOTE: This interface is specialised to the "added" type, other types must
    override fields as required.
    """

    families = List(
        Family,
        description="""Family definitions.""",
        args=DEF_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    family_proxies = List(
        FamilyProxy,
        description="""Family cycle instances.""",
        args=PROXY_ARGS,
        ghosts=Boolean(default_value=True),
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    jobs = List(
        Job,
        description="""Task jobs.""",
        args=JOB_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    tasks = List(
        Task,
        description="""Task definitions.""",
        args=DEF_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    task_proxies = List(
        TaskProxy,
        description="""Task cycle instances.""",
        args=PROXY_ARGS,
        ghosts=Boolean(default_value=True),
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        resolver=get_nodes_by_ids
    )
    edges = List(
        Edge,
        description="""Graph edges""",
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
        description = """Added node/edge deltas."""
        interfaces = (Delta,)


class Updated(ObjectType):
    class Meta:
        description = """Updated node/edge deltas."""
        interfaces = (Delta,)

    families = List(
        Family,
        description="""Family definitions.""",
        args=DEF_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    family_proxies = List(
        FamilyProxy,
        description="""Family cycle instances.""",
        args=PROXY_ARGS,
        ghosts=Boolean(default_value=False),
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    jobs = List(
        Job,
        description="""Task jobs.""",
        args=JOB_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    tasks = List(
        Task,
        description="""Task definitions.""",
        args=DEF_ARGS,
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    task_proxies = List(
        TaskProxy,
        description="""Task cycle instances.""",
        args=PROXY_ARGS,
        ghosts=Boolean(default_value=False),
        strip_null=Boolean(),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_UPDATED),
        resolver=get_nodes_by_ids
    )
    edges = List(
        Edge,
        description="""Graph edges""",
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
        description = """Grouped deltas of the WFS publish"""
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
        description = """Multi-Workflow root level subscriptions."""

    deltas = Field(
        Deltas,
        description=Deltas._meta.description,
        workflows=List(ID, description="List of full ID, i.e. `owner|name`"),
        strip_null=Boolean(default_value=False),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    workflows = List(
        Workflow,
        description=Workflow._meta.description,
        ids=List(ID, default_value=[]),
        exids=List(ID, default_value=[]),
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
    jobs = List(
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
    tasks = List(
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
        ghosts=Boolean(default_value=True),
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    task_proxies = List(
        TaskProxy,
        description=TaskProxy._meta.description,
        args=ALL_PROXY_ARGS,
        ghosts=Boolean(default_value=True),
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
    families = List(
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
        ghosts=Boolean(default_value=True),
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    family_proxies = List(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        args=ALL_PROXY_ARGS,
        ghosts=Boolean(default_value=True),
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )
    edges = List(
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
        ghosts=Boolean(default_value=True),
        strip_null=Boolean(default_value=True),
        delta_store=Boolean(default_value=True),
        delta_type=String(default_value=DELTA_ADDED),
        initial_burst=Boolean(default_value=True),
        ignore_interval=Float(default_value=0.0),
        resolver=delta_subs
    )


schema = Schema(query=Queries, subscription=Subscriptions, mutation=Mutations)

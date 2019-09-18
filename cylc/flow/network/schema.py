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

"""GraphQL API schema via Graphene implementation."""

from graphene import (
    Boolean, Field, Float, ID, InputObjectType, Int,
    List, Mutation, ObjectType, Schema, String, Union
)
from graphene.types.generic import GenericScalar
from graphene.utils.str_converters import to_snake_case

from cylc.flow.task_state import TASK_STATUSES_ORDERED
from cylc.flow.ws_data_mgr import (
    ID_DELIM, FAMILIES, FAMILY_PROXIES,
    JOBS, TASKS, TASK_PROXIES
)


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


jobs_args = dict(
    ids=List(ID, default_value=[]),
    exids=List(ID, default_value=[]),
    states=List(String, default_value=[]),
    exstates=List(String, default_value=[]),
    sort=SortArgs(default_value=None),
)

all_jobs_args = dict(
    workflows=List(ID, default_value=[]),
    exworkflows=List(ID, default_value=[]),
    ids=List(ID, default_value=[]),
    exids=List(ID, default_value=[]),
    states=List(String, default_value=[]),
    exstates=List(String, default_value=[]),
    sort=SortArgs(default_value=None),
)

def_args = dict(
    ids=List(ID, default_value=[]),
    exids=List(ID, default_value=[]),
    mindepth=Int(default_value=-1),
    maxdepth=Int(default_value=-1),
    sort=SortArgs(default_value=None),
)

all_def_args = dict(
    workflows=List(ID, default_value=[]),
    exworkflows=List(ID, default_value=[]),
    ids=List(ID, default_value=[]),
    exids=List(ID, default_value=[]),
    mindepth=Int(default_value=-1),
    maxdepth=Int(default_value=-1),
    sort=SortArgs(default_value=None),
)

proxy_args = dict(
    ghosts=Boolean(default_value=False),
    ids=List(ID, default_value=[]),
    exids=List(ID, default_value=[]),
    states=List(String, default_value=[]),
    exstates=List(String, default_value=[]),
    is_held=Boolean(),
    mindepth=Int(default_value=-1),
    maxdepth=Int(default_value=-1),
    sort=SortArgs(default_value=None),
)

all_proxy_args = dict(
    ghosts=Boolean(default_value=False),
    workflows=List(ID, default_value=[]),
    exworkflows=List(ID, default_value=[]),
    ids=List(ID, default_value=[]),
    exids=List(ID, default_value=[]),
    states=List(String, default_value=[]),
    exstates=List(String, default_value=[]),
    is_held=Boolean(),
    mindepth=Int(default_value=-1),
    maxdepth=Int(default_value=-1),
    sort=SortArgs(default_value=None),
)

edge_args = dict(
    ids=List(ID, default_value=[]),
    exids=List(ID, default_value=[]),
    states=List(String, default_value=[]),
    exstates=List(String, default_value=[]),
    mindepth=Int(default_value=-1),
    maxdepth=Int(default_value=-1),
    sort=SortArgs(default_value=None),
)

all_edge_args = dict(
    workflows=List(ID, default_value=[]),
    exworkflows=List(ID, default_value=[]),
    sort=SortArgs(default_value=None),
)

nodes_edges_args = dict(
    ghosts=Boolean(default_value=False),
    ids=List(ID, default_value=[]),
    exids=List(ID, default_value=[]),
    states=List(String, default_value=[]),
    exstates=List(String, default_value=[]),
    is_held=Boolean(),
    distance=Int(default_value=1),
    mindepth=Int(default_value=-1),
    maxdepth=Int(default_value=-1),
    sort=SortArgs(default_value=None),
)

nodes_edges_args_all = dict(
    ghosts=Boolean(default_value=False),
    workflows=List(ID, default_value=[]),
    exworkflows=List(ID, default_value=[]),
    ids=List(ID, default_value=[]),
    exids=List(ID, default_value=[]),
    states=List(String, default_value=[]),
    exstates=List(String, default_value=[]),
    is_held=Boolean(),
    distance=Int(default_value=1),
    mindepth=Int(default_value=-1),
    maxdepth=Int(default_value=-1),
    sort=SortArgs(default_value=None),
)

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


async def get_workflows(root, info, **args):
    args['workflows'] = [parse_workflow_id(w_id) for w_id in args['ids']]
    args['exworkflows'] = [parse_workflow_id(w_id) for w_id in args['exids']]
    resolvers = info.context.get('resolvers')
    return await resolvers.get_workflows(args)


async def get_nodes_all(root, info, **args):
    """Resolver for returning job, task, family nodes"""
    field_name = to_snake_case(info.field_name)
    field_ids = getattr(root, field_name, None)
    if hasattr(args, 'id'):
        args['ids'] = [args.get('id')]
    if field_ids:
        args['ids'] = field_ids
    elif field_ids == []:
        return []
    try:
        obj_type = str(info.return_type.of_type).replace('!', '')
    except AttributeError:
        obj_type = str(info.return_type)
    node_type = NODE_MAP[obj_type]
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
    field_name = to_snake_case(info.field_name)
    field_ids = getattr(root, field_name, None)
    if hasattr(args, 'id'):
        args['ids'] = [args.get('id')]
    if field_ids:
        if isinstance(field_ids, str):
            field_ids = [field_ids]
        args['native_ids'] = field_ids
    elif field_ids == []:
        return []
    try:
        obj_type = str(info.return_type.of_type).replace('!', '')
    except AttributeError:
        obj_type = str(info.return_type)
    node_type = NODE_MAP[obj_type]
    args['ids'] = [parse_node_id(n_id, node_type) for n_id in args['ids']]
    args['exids'] = [parse_node_id(n_id, node_type) for n_id in args['exids']]
    resolvers = info.context.get('resolvers')
    return await resolvers.get_nodes_by_ids(node_type, args)


async def get_node_by_id(root, info, **args):
    """Resolver for returning job, task, family node"""
    field_name = to_snake_case(info.field_name)
    if field_name == 'source_node':
        field_id = getattr(root, 'source', None)
    elif field_name == 'target_node':
        field_id = getattr(root, 'target', None)
    else:
        field_id = getattr(root, field_name, None)
    if field_id:
        args['id'] = field_id
    if args.get('id', None) is None:
        return None
    try:
        obj_type = str(info.return_type.of_type).replace('!', '')
    except AttributeError:
        obj_type = str(info.return_type)
    resolvers = info.context.get('resolvers')
    return await resolvers.get_node_by_id(NODE_MAP[obj_type], args)


async def get_edges_all(root, info, **args):
    args['workflows'] = [
        parse_workflow_id(w_id) for w_id in args['workflows']]
    args['exworkflows'] = [
        parse_workflow_id(w_id) for w_id in args['exworkflows']]
    resolvers = info.context.get('resolvers')
    return await resolvers.get_edges_all(args)


async def get_edges_by_ids(root, info, **args):
    field_name = to_snake_case(info.field_name)
    field_ids = getattr(root, field_name, None)
    if field_ids:
        args['native_ids'] = list(field_ids)
    elif field_ids == []:
        return []
    resolvers = info.context.get('resolvers')
    return await resolvers.get_edges_by_ids(args)


async def get_nodes_edges(root, info, **args):
    """Resolver for returning job, task, family nodes"""
    node_type = NODE_MAP['TaskProxy']
    workflow = getattr(root, 'id', None)
    if workflow:
        args['workflows'] = [parse_workflow_id(workflow)]
        args['exworkflows'] = []
    else:
        args['workflows'] = [
            parse_workflow_id(w_id) for w_id in args['workflows']]
        args['exworkflows'] = [
            parse_workflow_id(w_id) for w_id in args['exworkflows']]
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


# Types:
class DefMeta(ObjectType):
    class Meta:
        description = """
Meta data fields,
including custom fields in a generic userdefined dump"""
    title = String(default_value=None)
    description = String(default_value=None)
    URL = String(default_value=None)
    user_defined = List(String, default_value=[])


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
    id = ID(required=True)
    name = String()
    status = String()
    status_msg = String()
    host = String()
    port = Int()
    owner = String()
    tasks = List(
        lambda: Task,
        description="""Task definitions.""",
        args=def_args,
        resolver=get_nodes_by_ids)
    families = List(
        lambda: Family,
        description="""Family definitions.""",
        args=def_args,
        resolver=get_nodes_by_ids)
    task_proxies = List(
        lambda: TaskProxy,
        description="""Task cycle instances.""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    family_proxies = List(
        lambda: FamilyProxy,
        description="""Family cycle instances.""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    edges = Field(
        lambda: Edges,
        args=edge_args,
        description="""Graph edges""")
    nodes_edges = Field(
        lambda: NodesEdges,
        args=nodes_edges_args,
        resolver=get_nodes_edges)
    api_version = Int()
    cylc_version = String()
    last_updated = Float()
    meta = Field(DefMeta)
    newest_runahead_cycle_point = String()
    newest_cycle_point = String()
    oldest_cycle_point = String()
    reloading = Boolean()
    run_mode = String()
    is_held_total = Int()
    state_totals = GenericScalar(resolver=resolve_state_totals)
    workflow_log_dir = String()
    time_zone_info = Field(TimeZone)
    tree_depth = Int()
    ns_defn_order = List(String)
    job_log_names = List(String)
    states = List(String)


class Job(ObjectType):
    class Meta:
        description = """Jobs."""
    id = ID(required=True)
    submit_num = Int()
    state = String()
    # name and cycle_point for filtering/sorting
    name = String(required=True)
    cycle_point = String(required=True)
    task_proxy = Field(
        lambda: TaskProxy,
        description="""Associated Task Proxy""",
        required=True,
        resolver=get_node_by_id)
    submitted_time = String()
    started_time = String()
    finished_time = String()
    batch_sys_job_id = ID()
    batch_sys_name = String()
    env_script = String()
    err_script = String()
    exit_script = String()
    execution_time_limit = Float()
    host = String()
    init_script = String()
    job_log_dir = String()
    owner = String()
    post_script = String()
    pre_script = String()
    script = String()
    work_sub_dir = String()
    batch_sys_conf = List(String)
    environment = List(String)
    directives = List(String)
    param_env_tmpl = List(String)
    param_var = List(String)
    extra_logs = List(String)


class Task(ObjectType):
    class Meta:
        description = """Task definition, static fields"""
    id = ID(required=True)
    name = String(required=True)
    meta = Field(DefMeta)
    mean_elapsed_time = Float()
    depth = Int()
    proxies = List(
        lambda: TaskProxy,
        description="""Associated cycle point proxies""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    namespace = List(String, required=True)


class PollTask(ObjectType):
    class Meta:
        description = """Polling task edge"""
    local_proxy = ID(required=True)
    workflow = String()
    remote_proxy = ID(required=True)
    req_state = String()
    graph_string = String()


class Condition(ObjectType):
    class Meta:
        description = """Prerequisite conditions."""
    task_proxy = Field(
        lambda: TaskProxy,
        description="""Associated Task Proxy""",
        resolver=get_node_by_id)
    expr_alias = String()
    req_state = String()
    satisfied = Boolean()
    message = String()


class Prerequisite(ObjectType):
    class Meta:
        description = """Task prerequisite."""
    expression = String()
    conditions = List(
        Condition,
        description="""Condition monomers of a task prerequisites.""")
    cycle_points = List(String)
    satisfied = Boolean()


class TaskProxy(ObjectType):
    class Meta:
        description = """Task cycle instance."""
    id = ID(required=True)
    task = Field(
        Task,
        description="""Task definition""",
        required=True,
        resolver=get_node_by_id)
    state = String()
    cycle_point = String()
    is_held = Boolean()
    spawned = Boolean()
    depth = Int()
    job_submits = Int()
    latest_message = String()
    outputs = List(String, default_value=[])
    broadcasts = List(String, default_value=[])
    # name & namespace for filtering/sorting
    name = String(required=True)
    namespace = List(String, required=True)
    prerequisites = List(Prerequisite)
    jobs = List(
        Job,
        description="""Task jobs.""",
        args=jobs_args,
        resolver=get_nodes_by_ids)
    parents = List(
        lambda: FamilyProxy,
        description="""Task parents.""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    first_parent = Field(
        lambda: FamilyProxy,
        description="""Task first parent.""",
        args=proxy_args,
        resolver=get_node_by_id)


class Family(ObjectType):
    class Meta:
        description = """Task definition, static fields"""
    id = ID(required=True)
    name = String(required=True)
    meta = Field(DefMeta)
    depth = Int()
    proxies = List(
        lambda: FamilyProxy,
        description="""Associated cycle point proxies""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    parents = List(
        lambda: Family,
        description="""Family definition parent.""",
        args=def_args,
        resolver=get_nodes_by_ids)
    child_tasks = List(
        Task,
        description="""Descendedant definition tasks.""",
        args=def_args,
        resolver=get_nodes_by_ids)
    child_families = List(
        lambda: Family,
        description="""Descendedant desc families.""",
        args=def_args,
        resolver=get_nodes_by_ids)


class FamilyProxy(ObjectType):
    class Meta:
        description = """Family composite."""
    id = ID(required=True)
    cycle_point = String()
    # name & namespace for filtering/sorting
    name = String(required=True)
    family = Field(
        Family,
        description="""Family definition""",
        required=True,
        resolver=get_node_by_id)
    state = String()
    is_held = Boolean()
    depth = Int()
    parents = List(
        lambda: FamilyProxy,
        description="""Family parent proxies.""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    child_tasks = List(
        TaskProxy,
        description="""Descendedant task proxies.""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    child_families = List(
        lambda: FamilyProxy,
        description="""Descendedant family proxies.""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    first_parent = Field(
        lambda: FamilyProxy,
        description="""Task first parent.""",
        args=proxy_args,
        resolver=get_node_by_id)


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
    id = ID(required=True)
    source = ID()
    source_node = Field(
        Node,
        resolver=get_node_by_id)
    target = ID()
    target_node = Field(
        Node,
        resolver=get_node_by_id)
    suicide = Boolean()
    cond = Boolean()


class Edges(ObjectType):
    class Meta:
        description = """Dependency edge"""
    edges = List(
        Edge,
        required=True,
        args=edge_args,
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
        resolver=get_workflows)
    job = Field(
        Job,
        description=Job._meta.description,
        id=ID(required=True),
        resolver=get_node_by_id)
    jobs = List(
        Job,
        description=Job._meta.description,
        args=all_jobs_args,
        resolver=get_nodes_all)
    task = Field(
        Task,
        description=Task._meta.description,
        id=ID(required=True),
        resolver=get_node_by_id)
    tasks = List(
        Task,
        description=Task._meta.description,
        args=all_def_args,
        resolver=get_nodes_all)
    task_proxy = Field(
        TaskProxy,
        description=TaskProxy._meta.description,
        id=ID(required=True),
        resolver=get_node_by_id)
    task_proxies = List(
        TaskProxy,
        description=TaskProxy._meta.description,
        args=all_proxy_args,
        resolver=get_nodes_all)
    family = Field(
        Family,
        description=Family._meta.description,
        id=ID(required=True),
        resolver=get_node_by_id)
    families = List(
        Family,
        description=Family._meta.description,
        args=all_def_args,
        resolver=get_nodes_all)
    family_proxy = Field(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        id=ID(required=True),
        resolver=get_node_by_id)
    family_proxies = List(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        args=all_proxy_args,
        resolver=get_nodes_all)
    edges = List(
        Edge,
        description=Edge._meta.description,
        args=all_edge_args,
        resolver=get_edges_all)
    nodes_edges = Field(
        NodesEdges,
        description=NodesEdges._meta.description,
        args=nodes_edges_args_all,
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

async def mutator(root, info, command, workflows=None,
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


# Mutations defined:
class ClearBroadcast(Mutation):
    class Meta:
        description = """Expire all settings targeting cycle points
earlier than cutoff."""
        resolver = mutator

    class Arguments:
        workflows = List(String, required=True)
        command = String(default_value='clear_broadcast')
        point_strings = List(
            String,
            description="""`["*"]`""",
            default_value=['*'])
        namespaces = List(
            String,
            description="""namespaces: `["foo", "BAZ"]`""",)
        cancel_settings = List(
            GenericScalar,
            description="""
settings: `[{envronment: {ENVKEY: "env_val"}}, ...]`""",)

    result = GenericScalar()


class ExpireBroadcast(Mutation):
    class Meta:
        description = """Clear settings globally,
or for listed namespaces and/or points."""
        resolver = mutator

    class Arguments:
        workflows = List(String, required=True)
        command = String(default_value='expire_broadcast')
        cutoff = String(description="""String""")

    result = GenericScalar()


class HoldWorkflow(Mutation):
    class Meta:
        description = """Hold workflow.
- hold on workflow. (default)
- hold point of workflow."""
        resolver = mutator

    class Arguments:
        command = String(
            description="""options:
- `hold_suite` (default)
- `hold_after_point_string`""",
            default_value='hold_suite')
        point_string = String()
        workflows = List(String, required=True)

    result = GenericScalar()


class NudgeWorkflow(Mutation):
    class Meta:
        description = """Tell workflow to try task processing."""
        resolver = mutator

    class Arguments:
        command = String(default_value='nudge')
        workflows = List(String, required=True)

    result = GenericScalar()


class PutBroadcast(Mutation):
    class Meta:
        description = """Put up new broadcast settings
(server side interface)."""
        resolver = mutator

    class Arguments:
        command = String(default_value='put_broadcast')
        workflows = List(String, required=True)
        point_strings = List(
            String,
            description="""`["*"]`""",
            default_value=['*'])
        namespaces = List(
            String,
            description="""namespaces: `["foo", "BAZ"]`""",)
        settings = List(
            GenericScalar,
            description="""
settings: `[{envronment: {ENVKEY: "env_val"}}, ...]`""",)

    result = GenericScalar()


class PutMessages(Mutation):
    class Meta:
        description = """Put task messages in queue for processing
later by the main loop."""
        resolver = nodes_mutator

    class Arguments:
        workflows = List(String, required=True)
        command = String(default_value='put_messages')
        ids = List(
            String,
            description="""Task job in the form
`"CYCLE%TASK_NAME%SUBMIT_NUM"`""",
            required=True)
        event_time = String(default_value=None)
        messages = List(
            List(String),
            description="""List in the form `[[severity, message], ...]`.""",
            default_value=None)

    result = GenericScalar()


class ReleaseWorkflow(Mutation):
    class Meta:
        description = """Reload workflow definitions."""
        resolver = mutator

    class Arguments:
        command = String(default_value='release_suite')
        workflows = List(String, required=True)

    result = GenericScalar()


class ReloadWorkflow(Mutation):
    class Meta:
        description = """Tell workflow to reload the workflow definition."""
        resolver = mutator

    class Arguments:
        workflows = List(String, required=True)
        command = String(default_value='reload_suite')

    result = GenericScalar()


class SetVerbosity(Mutation):
    class Meta:
        description = """Set workflow verbosity to new level."""
        resolver = mutator

    class Arguments:
        workflows = List(String, required=True)
        command = String(default_value='set_verbosity')
        level = String(
            description="""levels:
`INFO`, `WARNING`, `NORMAL`, `CRITICAL`, `ERROR`, `DEBUG`""",
            required=True)

    result = GenericScalar()


class StopWorkflowArgs(InputObjectType):
    datetime_string = String(description="""ISO 8601 compatible or
`YYYY/MM/DD-HH:mm` of wallclock/real-world date-time""")
    point_string = String(description="""Workflow formated point string""")
    task_id = String()
    kill_active_tasks = Boolean(description="""Use with: set_stop_cleanly""")
    terminate = Boolean(description="""Use with: `stop_now`""")


class StopWorkflow(Mutation):
    class Meta:
        description = """Workflow stop actions:
- Cleanly or after kill active tasks. (default)
- After cycle point.
- After wallclock time.
- On event handler completion, or terminate right away.
- After an instance of a task."""
        resolver = mutator

    class Arguments:
        workflows = List(String, required=True)
        command = String(
            description="""String options:
- `set_stop_cleanly`  (default)
- `set_stop_after_clock_time`
- `set_stop_after_point`
- `set_stop_after_task`
- `stop_now`""",
            default_value='set_stop_cleanly',)
        args = StopWorkflowArgs()

    result = GenericScalar()


class TaskArgs(InputObjectType):
    check_syntax = Boolean(description="""Use with actions:
- `dry_run_tasks`""")
    no_check = Boolean(description="""Use with actions:
- `insert_tasks`""")
    stop_point_string = String(description="""Use with actions:
- `insert_tasks`""")
    poll_succ = Boolean(description="""Use with actions:
- `poll_tasks`""")
    spawn = Boolean(description="""Use with actions:
- `remove_tasks`""")
    state = String(description="""Use with actions:
- `reset_task_states`""")
    outputs = List(String, description="""Use with actions:
- `reset_task_states`""")
    back_out = Boolean(description="""Use with actions:
- `trigger_tasks`""")


class TaskActions(Mutation):
    class Meta:
        description = """Task actions:
- Prepare job file for task(s).
- Hold tasks.
- Insert task proxies.
- Kill task jobs.
- Return True if task_id exists (and running).
- Unhold tasks.
- Remove tasks from task pool.
- Reset statuses tasks.
- Spawn tasks.
- Trigger submission of task jobs where possible."""
        resolver = nodes_mutator

    class Arguments:
        workflows = List(String)
        command = String(
            description="""Task actions:
- `dry_run_tasks`
- `hold_tasks`
- `insert_tasks`
- `kill_tasks`
- `poll_tasks`
- `release_tasks`
- `remove_tasks`
- `reset_task_states`
- `spawn_tasks`
- `trigger_tasks`""",
            required=True,)
        ids = List(
            String,
            description="""Used with:
- All Commands

A list of identifiers (family%glob%id) for matching task proxies, i.e.
```
[
    "owner%workflow%201905*%foo",
    "foo.201901*:failed",
    "201901*%baa:failed",
    "FAM.20190101T0000Z",
    "FAM2",
    "*.20190101T0000Z"
]
```
(where % is the delimiter)

Splits argument into componnents, creates workflows argument if non-existent.
""",
            required=True)
        args = TaskArgs()

    result = GenericScalar()


class TakeCheckpoint(Mutation):
    class Meta:
        description = """Checkpoint current task pool."""
        resolver = mutator

    class Arguments:
        workflows = List(String, required=True)
        command = String(default_value='take_checkpoints')
        name = String(
            description="""The checkpoint name""",
            required=True,)

    result = GenericScalar()


class ExternalTrigger(Mutation):
    class Meta:
        description = """Server-side external event trigger interface."""
        resolver = mutator

    class Arguments:
        workflows = List(String, required=True)
        command = String(default_value='put_external_trigger')
        event_message = String(required=True)
        event_id = String(required=True)

    result = GenericScalar()


# Mutation declarations
class Mutations(ObjectType):
    clear_broadcast = ClearBroadcast.Field(
        description=ClearBroadcast._meta.description)
    expire_broadcast = ExpireBroadcast.Field(
        description=ExpireBroadcast._meta.description)
    put_broadcast = PutBroadcast.Field(
        description=PutBroadcast._meta.description)
    ext_trigger = ExternalTrigger.Field(
        description=ExternalTrigger._meta.description)
    hold_workflow = HoldWorkflow.Field(
        description=HoldWorkflow._meta.description)
    nudge_workflow = NudgeWorkflow.Field(
        description=NudgeWorkflow._meta.description)
    put_messages = PutMessages.Field(
        description=PutMessages._meta.description)
    release_workflow = ReleaseWorkflow.Field(
        description=ReleaseWorkflow._meta.description)
    reload_workflow = ReloadWorkflow.Field(
        description=ReloadWorkflow._meta.description)
    set_verbosity = SetVerbosity.Field(
        description=SetVerbosity._meta.description)
    stop_workflow = StopWorkflow.Field(
        description=StopWorkflow._meta.description)
    take_checkpoint = TakeCheckpoint.Field(
        description=TakeCheckpoint._meta.description)
    task_actions = TaskActions.Field(
        description=TaskActions._meta.description)


schema = Schema(query=Queries, mutation=Mutations)

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

"""GraphQL API schema via Graphene implementation."""

import asyncio
from functools import partial
import logging
from textwrap import dedent
from typing import Callable, AsyncGenerator, Any

from graphene import (
    Boolean, Field, Float, ID, InputObjectType, Int,
    List, Mutation, ObjectType, Schema, String, Union, Enum
)
from graphene.types.generic import GenericScalar
from graphene.utils.str_converters import to_snake_case

from cylc.flow.task_state import (
    TASK_STATUSES_ORDERED,
    TASK_STATUS_DESC,
    # TASK_STATUS_RUNAHEAD,
    TASK_STATUS_WAITING,
    TASK_STATUS_QUEUED,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_READY,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RETRYING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED
)
from cylc.flow.data_store_mgr import (
    ID_DELIM, FAMILIES, FAMILY_PROXIES,
    JOBS, TASKS, TASK_PROXIES
)
from cylc.flow.suite_status import StopMode


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
including custom fields in a generic user-defined dump"""
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
    reloaded = Boolean()
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
    messages = List(String)


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
    ancestors = List(
        lambda: FamilyProxy,
        description="""First parent ancestors.""",
        args=proxy_args,
        resolver=get_nodes_by_ids)


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
        description="""Descendant definition tasks.""",
        args=def_args,
        resolver=get_nodes_by_ids)
    child_families = List(
        lambda: Family,
        description="""Descendant desc families.""",
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
        description="""Descendant task proxies.""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    child_families = List(
        lambda: FamilyProxy,
        description="""Descendant family proxies.""",
        args=proxy_args,
        resolver=get_nodes_by_ids)
    first_parent = Field(
        lambda: FamilyProxy,
        description="""Task first parent.""",
        args=proxy_args,
        resolver=get_node_by_id)
    ancestors = List(
        lambda: FamilyProxy,
        description="""First parent ancestors.""",
        args=proxy_args,
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


class BroadcastSetting(InputObjectType):
    """A task/family runtime setting as a key, value pair."""

    key = RuntimeConfiguration(
        description=sstrip('''
            The cylc namespace for the setting to modify.
            e.g. `[environment]variable_name`.
        '''),
        required=True
    )
    value = String(
        description='The value of the modification',
        required=True
    )


class BroadcastMode(Enum):
    Set = 'put_broadcast'
    Clear = 'clear_broadcast'

    @property
    def description(self):
        if self == BroadcastMode.Set:
            return 'Create a new broadcast.'
        if self == BroadcastMode.Clear:
            return 'Revoke an existing broadcast.'
        return ''


class TaskStatus(Enum):
    """The status of a task in a workflow."""

    # NOTE: this is an enumeration purely for the GraphQL schema
    # TODO: the task statuses should be formally declared in a Python
    #       enumeration rendering this class unnecessary
    # NOTE: runahead purposefully omitted to hide users from the task pool
    # Runahead = TASK_STATUS_RUNAHEAD
    Waiting = TASK_STATUS_WAITING
    Queued = TASK_STATUS_QUEUED
    Expired = TASK_STATUS_EXPIRED
    Ready = TASK_STATUS_READY
    SubmitFailed = TASK_STATUS_SUBMIT_FAILED
    SubmitRetrying = TASK_STATUS_SUBMIT_RETRYING
    Submitted = TASK_STATUS_SUBMITTED
    Retrying = TASK_STATUS_RETRYING
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


class SuiteStopMode(Enum):
    """The mode used to stop a running workflow."""

    # Note: contains only the REQUEST_* values from StopMode
    Clean = StopMode.REQUEST_CLEAN
    Now = StopMode.REQUEST_NOW
    NowNow = StopMode.REQUEST_NOW_NOW

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
            Override or add new [runtime] config in targeted namespaces in
            a running suite.

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

            Broadcasts persist, even across suite restarts, until they expire
            when their target cycle point is older than the oldest current in
            the suite, or until they are explicitly cancelled with this
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
            default_value=1,
            required=True
        )
        cycle_points = List(
            CyclePoint,
            description=sstrip('''
                List of cycle points to target or `*` to cancel all all-cycle
                broadcasts without canceling all specific-cycle broadcasts.
            '''),
            default_value=['*'])
        tasks = List(
            NamespaceName,
            description='Target namespaces.',
            default_value=['root']
        )
        settings = List(
            BroadcastSetting,
            description='Target settings.'
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


class Hold(Mutation):
    class Meta:
        description = sstrip('''
            Hold a workflow or tasks within it.
        ''')
        resolver = partial(mutator, command='hold')

    class Arguments:
        workflows = List(WorkflowID, required=True)
        tasks = List(
            NamespaceIDGlob,
            description='Hold the specified tasks rather than the workflow.'
        )
        time = TimePoint(description=sstrip('''
            Get the workflow to hold after the specified wallclock time
            has passed.
        '''))

    result = GenericScalar()


class Nudge(Mutation):
    class Meta:
        description = sstrip('''
            Cause the Cylc task processing loop to be invoked on a running
            suite.

            This happens automatically when the state of any task changes
            such that task processing (dependency negotiation etc.)
            is required, or if a clock-trigger task is ready to run.
        ''')
        resolver = partial(mutator, command='nudge')

    class Arguments:
        workflows = List(WorkflowID, required=True)

    result = GenericScalar()


class Ping(Mutation):
    class Meta:
        description = sstrip('''
            Send a test message to a running suite.
        ''')
        resolver = partial(mutator, command='ping_suite')

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
            - The suite server program, if communication is possible.

            Task jobs use this to record and report status such
            as success and failure. Applications run by task jobs can use
            this command to report messages and to report registered task
            outputs.
        ''')
        resolver = partial(nodes_mutator, command='put_messages')

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


class Release(Mutation):
    class Meta:
        description = sstrip('''
            Release a held workflow or tasks within it.

            See also the opposite command `hold`.
        ''')
        resolver = partial(mutator, command='release')

    class Arguments:
        workflows = List(WorkflowID, required=True)
        tasks = List(
            NamespaceIDGlob,
            description=sstrip('''
                Release matching tasks rather than the workflow as whole.
            ''')
        )

    result = GenericScalar()


class Reload(Mutation):
    class Meta:
        description = sstrip('''
            Tell a suite to reload its definition at run time.

            All settings including task definitions, with the
            exception of suite log configuration, can be changed on reload.
            Note that defined tasks can be be added to or removed from a
            running suite using "insert" and "remove" without reloading.  This
            command also allows addition and removal of actual task
            definitions, and therefore insertion of tasks that were not defined
            at all when the suite started (you will still need to manually
            insert a particular instance of a newly defined task). Live task
            proxies that are orphaned by a reload (i.e. their task definitions
            have been removed) will be removed from the task pool if they have
            not started running yet. Changes to task definitions take effect
            immediately, unless a task is already running at reload time.

            If the suite was started with Jinja2 template variables
            set on the command line (cylc run --set FOO=bar REG) the same
            template settings apply to the reload (only changes to the suite.rc
            file itself are reloaded).

            If the modified suite definition does not parse,
            failure to reload will be reported but no harm will be done to the
            running suite.
        ''')
        resolver = partial(mutator, command='reload_suite')

    class Arguments:
        workflows = List(WorkflowID, required=True)

    result = GenericScalar()


class SetVerbosity(Mutation):
    class Meta:
        description = sstrip('''
            Change the logging severity level of a running suite.

            Only messages at or above the chosen severity level will be logged;
            for example, if you choose `WARNING`, only warnings and critical
            messages will be logged.
        ''')
        resolver = partial(mutator, command='set_verbosity')

    class Arguments:
        workflows = List(WorkflowID, required=True)
        level = LogLevels(required=True)

    result = GenericScalar()


class Stop(Mutation):
    class Meta:
        description = sstrip(f'''
            Tell a suite server program to shut down.

            By default suites wait for all submitted and running tasks to
            complete before shutting down. You can change this behaviour
            with the "mode" option.
        ''')
        resolver = partial(mutator, command='stop_workflow')

    class Arguments:
        workflows = List(WorkflowID, required=True)
        mode = SuiteStopMode(
            # TODO default
        )
        cycle_point = CyclePoint(
            description='Stop after the suite reaches this cycle.'
        )
        clock_time = TimePoint(
            description='Stop after wall-clock time passes this point.'
        )
        task = TaskID(
            description='Stop after this task succeeds.'
        )

    result = GenericScalar()


class Checkpoint(Mutation):
    class Meta:
        description = 'Tell the suite to checkpoint its current state.'
        resolver = partial(mutator, command='take_checkpoints')

    class Arguments:
        workflows = List(WorkflowID, required=True)
        name = String(
            description='The checkpoint name.',
            required=True
        )

    result = GenericScalar()


class ExtTrigger(Mutation):
    class Meta:
        description = sstrip('''
            Report an external event message to a suite server program.

            It is expected that a task in the suite has registered the same
            message as an external trigger - a special prerequisite to be
            satisfied by an external system, via this command, rather than by
            triggering off other tasks.

            The ID argument should uniquely distinguish one external trigger
            event from the next. When a task's external trigger is satisfied by
            an incoming message, the message ID is broadcast to all downstream
            tasks in the cycle point as `$CYLC_EXT_TRIGGER_ID` so that they can
            use it - e.g. to identify a new data file that the external
            triggering system is responding to.

            Use the retry options in case the target suite is down or out of
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
        id = String(
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


class DryRun(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            [For internal use] Prepare the job file for a task.
        ''')
        resolver = partial(mutator, command='dry_run_tasks')

    class Arguments(TaskMutation.Arguments):
        check_syntax = Boolean(
            description='Check shell syntax.',
            default_value=True
        )


class Insert(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Insert new task proxies into the task pool of a running workflow.

            For example to enable re-triggering earlier tasks already removed
            from the pool.

            Note: inserted cycling tasks cycle on as normal, even if another
            instance of the same task exists at a later cycle (instances of the
            same task at different cycles can coexist, but a newly spawned task
            will not be added to the pool if it catches up to another task with
            the same ID).

            See also "Submit", for running tasks without the scheduler.
        ''')
        resolver = partial(mutator, command='insert_tasks')

    class Arguments(TaskMutation.Arguments):
        check_point = Boolean(
            description=sstrip('''
                Check that the provided cycle point is on one of the task's
                recurrences as defined in the suite configuration before
                inserting.
            '''),
            default_value=True
        )
        stop_point = CyclePoint(
            description='hold/stop cycle point for inserted task.'
        )


class Kill(Mutation, TaskMutation):
    # TODO: This should be a job mutation?
    class Meta:
        description = sstrip('''
            Kill jobs of active tasks and update their statuses accordingly.
        ''')
        resolver = partial(mutator, command='kill_tasks')


class Poll(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Poll (query) task jobs to verify and update their statuses.
        ''')
        resolver = partial(mutator, command='poll_tasks')

    class Arguments(TaskMutation.Arguments):
        poll_succeeded = Boolean(
            description='Allow polling of succeeded tasks.',
            default_value=False
        )


class Remove(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Remove one or more task instances from a running workflow.

            Tasks will be forced to spawn successors before removal if they
            have not done so already, unless you change the `spawn` option.
        ''')
        resolver = partial(mutator, command='remove_tasks')

    class Arguments(TaskMutation.Arguments):
        spawn = Boolean(
            description='Spawn successors before removal.',
            default_value=True
        )


class Reset(Mutation, TaskMutation):
    class Meta:
        description = sstrip(f'''
            Force task instances to a specified state.

            Outputs are automatically updated to reflect the new task state,
            except for custom message outputs which can be manipulated directly
            with `outputs`.

            Prerequisites reflect the state of other tasks; they are not
            changed except to unset them on resetting state to
            `{TASK_STATUS_WAITING}` or earlier.

            Note: To hold and release tasks use "Hold" and "Release", not this
            command.
        ''')
        resolver = partial(mutator, command='reset_task_states')

    class Arguments(TaskMutation.Arguments):
        state = TaskStatus(
            description='Reset the task status to this.'
        )
        outputs = List(
            String,
            description=sstrip('''
                Find task output by message string or trigger string, set
                complete or incomplete with `!OUTPUT`, `*` to set all
                complete, `!*` to set all incomplete.
            ''')
        )


class Spawn(Mutation, TaskMutation):
    class Meta:
        description = sstrip(f'''
            Force task proxies to spawn successors at their own next cycle
            point.

            Tasks normally spawn on reaching the {TASK_STATUS_SUBMITTED}
            status. Spawning them early allows running successive instances of
            the same task out of order.  See also the `spawn to max active
            cycle points` workflow configuration.

            Note this command does not operate on tasks at any arbitrary point
            in the abstract workflow graph - tasks not already in the pool must
            be inserted first with "Insert".
        ''')
        resolver = partial(mutator, command='spawn_tasks')


class Trigger(Mutation, TaskMutation):
    class Meta:
        description = sstrip('''
            Manually trigger tasks.

            TODO: re-implement edit funtionality!

            For single tasks you can use `edit` to edit the generated job
            script before it submits, to apply one-off changes. A diff between
            the original and edited job script will be saved to the task job
            log directory.

            Warning: waiting tasks that are queue-limited will be queued if
            triggered, to submit as normal when released by the queue; queued
            tasks will submit immediately if triggered, even if that violates
            the queue limit (so you may need to trigger a queue-limited task
            twice to get it to submit immediately).

            Note: tasks not already in the pool must be inserted first with
            "Insert" in order to be matched.
        ''')
        resolver = partial(mutator, command='trigger_tasks')

    class Arguments(TaskMutation.Arguments):
        # back_out = Boolean()
        # TODO: remove or re-implement?
        pass


# Mutation declarations

class Mutations(ObjectType):
    # workflow actions
    broadcast = Broadcast.Field(description=Message._meta.description)
    ext_trigger = ExtTrigger.Field(
        description=ExtTrigger._meta.description)
    hold = Hold.Field(description=Hold._meta.description)
    nudge = Nudge.Field(description=Nudge._meta.description)
    message = Message.Field(description=Message._meta.description)
    ping = Ping.Field(description=Ping._meta.description)
    release = Release.Field(description=Release._meta.description)
    reload = Reload.Field(description=Reload._meta.description)
    set_verbosity = SetVerbosity.Field(
        description=SetVerbosity._meta.description)
    stop = Stop.Field(description=Stop._meta.description)
    checkpoint = Checkpoint.Field(
        description=Checkpoint._meta.description)

    # task actions
    dry_run = DryRun.Field(description=DryRun._meta.description)
    insert = Insert.Field(description=Insert._meta.description)
    kill = Kill.Field(description=Kill._meta.description)
    poll = Poll.Field(description=Poll._meta.description)
    remove = Remove.Field(description=Remove._meta.description)
    reset = Reset.Field(description=Reset._meta.description)
    spawn = Spawn.Field(description=Spawn._meta.description)
    trigger = Trigger.Field(description=Trigger._meta.description)

    # job actions
    # TODO


# ** Subscription Related ** #

def to_subscription(func: Callable, sleep_seconds: float = 5.) -> Callable:
    """Wraps a function in a while-true-sleep, transforming
    the function into an async-generator, used by the
    websockets/subscriptions.

    Args:
        func (Callable): a callable.
        sleep_seconds (float): asyncio sleep interval in seconds.
    Returns:
        Callable: a callable async-generator wrapping the original callable.
    """
    async def gen(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        """
        Args:
            *args: Variable length argument list, varies as per schema.
            **kwargs: Arbitrary keyword arguments, varies as per schema.
        Returns:
            AsyncGenerator[Any, None]: an async generator that will
                yield values from resolvers.
        """
        while True:
            yield await func(*args, **kwargs)
            await asyncio.sleep(sleep_seconds)
    return gen


class Subscriptions(ObjectType):
    """Defines the subscriptions available in the schema."""
    class Meta:
        description = """Multi-Workflow root level subscriptions."""
    workflows = List(
        Workflow,
        description=Workflow._meta.description,
        ids=List(ID, default_value=[]),
        exids=List(ID, default_value=[]),
        resolver=to_subscription(get_workflows))
    job = Field(
        Job,
        description=Job._meta.description,
        id=ID(required=True),
        resolver=to_subscription(get_node_by_id))
    jobs = List(
        Job,
        description=Job._meta.description,
        args=all_jobs_args,
        resolver=to_subscription(get_nodes_all))
    task = Field(
        Task,
        description=Task._meta.description,
        id=ID(required=True),
        resolver=to_subscription(get_node_by_id))
    tasks = List(
        Task,
        description=Task._meta.description,
        args=all_def_args,
        resolver=to_subscription(get_nodes_all))
    task_proxy = Field(
        TaskProxy,
        description=TaskProxy._meta.description,
        id=ID(required=True),
        resolver=to_subscription(get_node_by_id))
    task_proxies = List(
        TaskProxy,
        description=TaskProxy._meta.description,
        args=all_proxy_args,
        resolver=to_subscription(get_nodes_all))
    family = Field(
        Family,
        description=Family._meta.description,
        id=ID(required=True),
        resolver=to_subscription(get_node_by_id))
    families = List(
        Family,
        description=Family._meta.description,
        args=all_def_args,
        resolver=to_subscription(get_nodes_all))
    family_proxy = Field(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        id=ID(required=True),
        resolver=to_subscription(get_node_by_id))
    family_proxies = List(
        FamilyProxy,
        description=FamilyProxy._meta.description,
        args=all_proxy_args,
        resolver=to_subscription(get_nodes_all))
    edges = List(
        Edge,
        description=Edge._meta.description,
        args=all_edge_args,
        resolver=to_subscription(get_edges_all))
    nodes_edges = Field(
        NodesEdges,
        description=NodesEdges._meta.description,
        args=nodes_edges_args_all,
        resolver=to_subscription(get_nodes_edges))


schema = Schema(query=Queries, subscription=Subscriptions, mutation=Mutations)

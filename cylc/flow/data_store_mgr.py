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
"""Manage the workflow data store.

The data store is generated here, in a Workflow Service (WS), and synced to the
User Interface Server (UIS) via protobuf messages. Used as resolving data with
GraphQL, both in the WS and UIS, it is then provisioned to the CLI and GUI.

This data store is comprised of Protobuf message objects (data elements),
which are used as data containers for their respective type.

Changes to the data store are accumulated on a main loop iteration as deltas
in the form of protobuf messages, and then applied to the local data-store.
These deltas are populated with the minimal information; only the elements
and only the fields of those elements that have changed. It is done this way
for the efficient transport and consistent application to remotely synced
data-stores.

Static data elements are generated on workflow start/restart/reload, which
includes workflow, task, and family definition objects.

The cycle point nodes/edges (i.e. task/family proxies) generation is triggered
individually on transition from staging to active task pool. Each active task
is generated along with any children and parents recursively out to a
specified maximum graph distance (n_edge_distance), that can be externally
altered (via API). Collectively this forms the N-Distance-Window on the
workflow graph.

Pruning of data-store elements is done using both the collection/set of nodes
generated through the associated graph paths of the active nodes and the
tracking of the boundary nodes (n_edge_distance+1) of those active nodes.
Once active, these boundary nodes act as the prune trigger for their
original/generator node(s). Set operations are used to do a diff between the
nodes of active paths (paths whose node is in the active task pool) and the
nodes of flagged paths (whose boundary node(s) have become active).

Updates are created by the event/task/job managers.

Data elements include a "stamp" field, which is a timestamped ID for use
in assessing changes in the data store, for comparisons of a store sync.

Packaging methods are included for dissemination of protobuf messages.

"""

from collections import Counter, deque
from copy import deepcopy
import json
from time import time
import zlib

from cylc.flow import __version__ as CYLC_VERSION, LOG, ID_DELIM
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.data_messages_pb2 import (  # type: ignore
    PbEdge, PbEntireWorkflow, PbFamily, PbFamilyProxy, PbJob, PbTask,
    PbTaskProxy, PbWorkflow, AllDeltas, EDeltas, FDeltas, FPDeltas,
    JDeltas, TDeltas, TPDeltas, WDeltas)
from cylc.flow.network import API
from cylc.flow.workflow_status import get_workflow_status
from cylc.flow.task_job_logs import JOB_LOG_OPTS, get_task_job_log
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import (
    TASK_STATUS_WAITING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_EXPIRED,
    TASK_STATUSES_ORDERED
)
from cylc.flow.task_state_prop import extract_group_state
from cylc.flow.taskdef import generate_graph_parents
from cylc.flow.task_state import TASK_STATUSES_FINAL
from cylc.flow.wallclock import (
    TIME_ZONE_LOCAL_INFO,
    TIME_ZONE_UTC_INFO,
    get_utc_mode,
    get_time_string_from_unix_time as time2str
)


EDGES = 'edges'
FAMILIES = 'families'
FAMILY_PROXIES = 'family_proxies'
JOBS = 'jobs'
TASKS = 'tasks'
TASK_PROXIES = 'task_proxies'
WORKFLOW = 'workflow'
ALL_DELTAS = 'all'
DELTA_ADDED = 'added'
DELTA_UPDATED = 'updated'
DELTA_PRUNED = 'pruned'
LATEST_STATE_TASKS_QUEUE_SIZE = 5

MESSAGE_MAP = {
    EDGES: PbEdge,
    FAMILIES: PbFamily,
    FAMILY_PROXIES: PbFamilyProxy,
    JOBS: PbJob,
    TASKS: PbTask,
    TASK_PROXIES: PbTaskProxy,
    WORKFLOW: PbWorkflow,
}

DATA_TEMPLATE = {
    EDGES: {},
    FAMILIES: {},
    FAMILY_PROXIES: {},
    JOBS: {},
    TASKS: {},
    TASK_PROXIES: {},
    WORKFLOW: PbWorkflow(),
}

DELTAS_MAP = {
    EDGES: EDeltas,
    FAMILIES: FDeltas,
    FAMILY_PROXIES: FPDeltas,
    JOBS: JDeltas,
    TASKS: TDeltas,
    TASK_PROXIES: TPDeltas,
    WORKFLOW: WDeltas,
    ALL_DELTAS: AllDeltas,
}

DELTA_FIELDS = {DELTA_ADDED, DELTA_UPDATED, DELTA_PRUNED}

JOB_STATUSES_ALL = [
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
]

# Faster lookup where order not needed.
JOB_STATUS_SET = set(JOB_STATUSES_ALL)

# Protobuf message merging appends repeated field results on merge,
# unlike singular fields which are overwritten. This behaviour is
# desirable in many cases, but there are exceptions.
# The following is used to flag which fields require clearing before
# merging from respective deltas messages.
CLEAR_FIELD_MAP = {
    EDGES: set(),
    FAMILIES: set(),
    FAMILY_PROXIES: {'state_totals', 'states'},
    JOBS: set(),
    TASKS: set(),
    TASK_PROXIES: {'prerequisites'},
    WORKFLOW: {'latest_state_tasks', 'state_totals', 'states'},
}


def parse_job_item(item):
    """Parse internal job id.

    Args:
        item (str):
            point/name/submit_num
            OR name.point.submit_num syntax.
    Returns:
        tuple - (point_str: str, name_str: str, submit_num: [int, None])

    """
    # BACK COMPAT: name.point.submit_num
    # url:
    #     https://github.com/cylc/cylc-admin/pull/115
    # from:
    #     Cylc7
    # to:
    #     Cylc8
    # remove at:
    #     Cylc9
    submit_num = None
    if item.count('/') > 1:
        point_str, name_str, submit_num = item.split('/', 2)
    elif '/' in item:
        point_str, name_str = item.split('/', 1)
    elif item.count('.') > 1:
        name_str, point_str, submit_num = item.split('.', 2)
    elif '.' in item:
        name_str, point_str = item.split('.', 1)
    else:
        name_str, point_str = (item, None)
    try:
        sub_num = int(submit_num)
    except (TypeError, ValueError):
        sub_num = None
    return (point_str, name_str, sub_num)


def generate_checksum(in_strings):
    """Generate cross platform & python checksum from strings."""
    # can't use hash(), it's not the same across 32-64bit or python invocations
    return zlib.adler32(''.join(sorted(in_strings)).encode()) & 0xffffffff


def task_mean_elapsed_time(tdef):
    """Calculate task mean elapsed time."""
    if tdef.elapsed_times:
        return sum(tdef.elapsed_times) / len(tdef.elapsed_times)
    return tdef.rtconfig.get('execution time limit', None)


def apply_delta(key, delta, data):
    """Apply delta to specific data-store workflow and type."""
    # Assimilate new data
    if getattr(delta, 'added', False):
        if key != WORKFLOW:
            data[key].update({e.id: e for e in delta.added})
        elif delta.added.ListFields():
            data[key].CopyFrom(delta.added)
    # Merge in updated fields
    if getattr(delta, 'updated', False):
        if key == WORKFLOW:
            # Clear fields that require overwrite with delta
            field_set = {f.name for f, _ in delta.updated.ListFields()}
            for field in CLEAR_FIELD_MAP[key]:
                if field in field_set:
                    data[key].ClearField(field)
            data[key].MergeFrom(delta.updated)
        else:
            for element in delta.updated:
                try:
                    data_element = data[key][element.id]
                    # Clear fields that require overwrite with delta
                    if CLEAR_FIELD_MAP[key]:
                        for field, _ in element.ListFields():
                            if field.name in CLEAR_FIELD_MAP[key]:
                                data_element.ClearField(field.name)
                    data_element.MergeFrom(element)
                except KeyError as exc:
                    # Ensure data-sync doesn't fail with
                    # network issues, sync reconcile/validate will catch.
                    LOG.debug(
                        'Missing Data-Store element '
                        'on update application: %s' % str(exc)
                    )
                    continue
    # Prune data elements
    if hasattr(delta, 'pruned'):
        # UIS flag to prune workflow, set externally.
        if key == WORKFLOW:
            if delta.HasField('pruned'):
                data[WORKFLOW].pruned = True
            return
        # Prune data elements by id
        for del_id in delta.pruned:
            if del_id not in data[key]:
                continue
            # remove relationships
            if key == TASK_PROXIES:
                # remove relationship from task
                data[TASKS][data[key][del_id].task].proxies.remove(del_id)
                # remove relationship from parent/family
                try:
                    data[FAMILY_PROXIES][
                        data[key][del_id].first_parent
                    ].child_tasks.remove(del_id)
                except KeyError:
                    pass
                # remove relationship from workflow
                getattr(data[WORKFLOW], key).remove(del_id)
            elif key == FAMILY_PROXIES:
                data[FAMILIES][data[key][del_id].family].proxies.remove(del_id)
                try:
                    data[FAMILY_PROXIES][
                        data[key][del_id].first_parent
                    ].child_families.remove(del_id)
                except KeyError:
                    pass
                getattr(data[WORKFLOW], key).remove(del_id)
            elif key == EDGES:
                edge = data[key][del_id]
                if edge.source in data[TASK_PROXIES]:
                    data[TASK_PROXIES][edge.source].edges.remove(del_id)
                if edge.target in data[TASK_PROXIES]:
                    data[TASK_PROXIES][edge.target].edges.remove(del_id)
                getattr(data[WORKFLOW], key).edges.remove(del_id)
            elif key == JOBS:
                # Jobs are only removed if their task is, so only need
                # to remove relationship from workflow.
                getattr(data[WORKFLOW], key).remove(del_id)
            # remove/prune element from data-store
            del data[key][del_id]


def create_delta_store(delta=None, workflow_id=None):
    """Create a mini data-store out of the all deltas message.

    Args:
        delta (cylc.flow.data_messages_pb2.AllDeltas):
            The message of accumulated deltas for publish/push.
        workflow_id (str):
            The workflow ID.

    Returns:
        dict

    """
    if not isinstance(delta, AllDeltas):
        delta = AllDeltas()
    delta_store = {
        DELTA_ADDED: deepcopy(DATA_TEMPLATE),
        DELTA_UPDATED: deepcopy(DATA_TEMPLATE),
        DELTA_PRUNED: {
            key: []
            for key in DATA_TEMPLATE.keys()
            if key is not WORKFLOW
        },
    }
    if workflow_id is not None:
        delta_store['id'] = workflow_id
    # ListFields returns a list fields that have been set (not all).
    for field, value in delta.ListFields():
        for sub_field, sub_value in value.ListFields():
            if sub_field.name in delta_store:
                if (
                        field.name == WORKFLOW
                        or sub_field.name == DELTA_PRUNED
                ):
                    field_data = sub_value
                else:
                    field_data = {
                        s.id: s
                        for s in sub_value
                    }
                delta_store[sub_field.name][field.name] = field_data
    return delta_store


class DataStoreMgr:
    """Manage the workflow data store.

    Attributes:
        .ancestors (dict):
            Local store of config.get_first_parent_ancestors()
        .data (dict):
            .edges (dict):
                cylc.flow.data_messages_pb2.PbEdge by internal ID.
            .families (dict):
                cylc.flow.data_messages_pb2.PbFamily by name (internal ID).
            .family_proxies (dict):
                cylc.flow.data_messages_pb2.PbFamilyProxy by internal ID.
            .jobs (dict):
                cylc.flow.data_messages_pb2.PbJob by internal ID.
            .tasks (dict):
                cylc.flow.data_messages_pb2.PbTask by name (internal ID).
            .task_proxies (dict):
                cylc.flow.data_messages_pb2.PbTaskProxy by internal ID.
            .workflow (cylc.flow.data_messages_pb2.PbWorkflow)
                Message containing the global information of the workflow.
        .descendants (dict):
            Local store of config.get_first_parent_descendants()
        .n_edge_distance (int):
            Maximum distance of the data-store graph from the active pool.
        .parents (dict):
            Local store of config.get_parent_lists()
        .publish_deltas (list):
            Collection of the latest applied deltas for publishing.
        .schd (cylc.flow.scheduler.Scheduler):
            Workflow scheduler object.
        .workflow_id (str):
            ID of the workflow service containing owner and name.

    Arguments:
        schd (cylc.flow.scheduler.Scheduler):
            Workflow scheduler instance.
    """

    ERR_PREFIX_JOBID_MATCH = 'No matching jobs found: '
    ERR_PREFIX_JOB_NOT_ON_SEQUENCE = 'Invalid cycle point for job: '

    def __init__(self, schd):
        self.schd = schd
        self.workflow_id = f'{self.schd.owner}{ID_DELIM}{self.schd.workflow}'
        self.ancestors = {}
        self.descendants = {}
        self.parents = {}
        self.state_update_families = set()
        self.updated_state_families = set()
        self.n_edge_distance = 1
        self.next_n_edge_distance = None
        self.latest_state_tasks = {
            state: deque(maxlen=LATEST_STATE_TASKS_QUEUE_SIZE)
            for state in TASK_STATUSES_ORDERED
        }
        self.xtrigger_tasks = {}
        # Managed data types
        self.data = {
            self.workflow_id: deepcopy(DATA_TEMPLATE)
        }
        self.added = deepcopy(DATA_TEMPLATE)
        self.updated = deepcopy(DATA_TEMPLATE)
        self.deltas = {
            EDGES: EDeltas(),
            FAMILIES: FDeltas(),
            FAMILY_PROXIES: FPDeltas(),
            JOBS: JDeltas(),
            TASKS: TDeltas(),
            TASK_PROXIES: TPDeltas(),
            WORKFLOW: WDeltas(),
        }
        # internal delta
        self.delta_queues = {self.workflow_id: {}}
        self.publish_deltas = []
        # internal n-window
        self.all_task_pool = set()
        self.n_window_nodes = {}
        self.n_window_edges = {}
        self.n_window_boundary_nodes = {}
        self.family_pruned_ids = set()
        self.prune_trigger_nodes = {}
        self.prune_flagged_nodes = set()
        self.updates_pending = False

    def initiate_data_model(self, reloaded=False):
        """Initiate or Update data model on start/restart/reload.

        Args:
            reloaded (bool, optional):
                Reset data-store before regenerating.

        """
        # Reset attributes/data-store on reload:
        if reloaded:
            self.__init__(self.schd)

        # Static elements
        self.generate_definition_elements()

        # Update workflow statuses and totals (assume needed)
        self.update_workflow()

        # Apply current deltas
        self.apply_deltas(reloaded)
        self.updates_pending = False

        # Gather this batch of deltas for publish
        self.publish_deltas = self.get_publish_deltas()

        # Clear deltas after application and publishing
        self.clear_deltas()

    def generate_definition_elements(self):
        """Generate static definition data elements.

        Populates the tasks, families, and workflow elements
        with data from and/or derived from the workflow definition.

        """
        config = self.schd.config
        update_time = time()
        tasks = self.added[TASKS]
        families = self.added[FAMILIES]
        workflow = self.added[WORKFLOW]
        workflow.id = self.workflow_id
        workflow.last_updated = update_time
        workflow.stamp = f'{workflow.id}@{workflow.last_updated}'

        graph = workflow.edges
        graph.leaves[:] = config.leaves
        graph.feet[:] = config.feet
        for key, info in config.workflow_polling_tasks.items():
            graph.workflow_polling_tasks.add(
                local_proxy=key,
                workflow=info[0],
                remote_proxy=info[1],
                req_state=info[2],
                graph_string=info[3],
            )

        ancestors = config.get_first_parent_ancestors()
        descendants = config.get_first_parent_descendants()
        parents = config.get_parent_lists()

        # Create definition elements for graphed tasks.
        for name, tdef in config.taskdefs.items():
            t_id = f'{self.workflow_id}{ID_DELIM}{name}'
            t_stamp = f'{t_id}@{update_time}'
            task = PbTask(
                stamp=t_stamp,
                id=t_id,
                name=name,
                depth=len(ancestors[name]) - 1,
            )
            task.namespace[:] = tdef.namespace_hierarchy
            task.first_parent = (
                f'{self.workflow_id}{ID_DELIM}{ancestors[name][1]}')
            user_defined_meta = {}
            for key, val in dict(tdef.describe()).items():
                if key in ['title', 'description', 'URL']:
                    setattr(task.meta, key, val)
                else:
                    user_defined_meta[key] = val
            task.meta.user_defined = json.dumps(user_defined_meta)
            elapsed_time = task_mean_elapsed_time(tdef)
            if elapsed_time:
                task.mean_elapsed_time = elapsed_time
            task.parents.extend(
                [f'{self.workflow_id}{ID_DELIM}{p_name}'
                 for p_name in parents[name]])
            tasks[t_id] = task

        # Created family definition elements for first parent
        # ancestors of graphed tasks.
        for key, names in ancestors.items():
            for name in names:
                if (
                        key == name or
                        name in families
                ):
                    continue
                f_id = f'{self.workflow_id}{ID_DELIM}{name}'
                f_stamp = f'{f_id}@{update_time}'
                family = PbFamily(
                    stamp=f_stamp,
                    id=f_id,
                    name=name,
                    depth=len(ancestors[name]) - 1,
                )
                famcfg = config.cfg['runtime'][name]
                user_defined_meta = {}
                for key, val in famcfg.get('meta', {}).items():
                    if key in ['title', 'description', 'URL']:
                        setattr(family.meta, key, val)
                    else:
                        user_defined_meta[key] = val
                family.meta.user_defined = json.dumps(user_defined_meta)
                family.parents.extend(
                    [f'{self.workflow_id}{ID_DELIM}{p_name}'
                     for p_name in parents[name]])
                try:
                    family.first_parent = (
                        f'{self.workflow_id}{ID_DELIM}{ancestors[name][1]}')
                except IndexError:
                    pass
                families[f_id] = family

        for name, parent_list in parents.items():
            if not parent_list:
                continue
            fam = parent_list[0]
            f_id = f'{self.workflow_id}{ID_DELIM}{fam}'
            if f_id in families:
                ch_id = f'{self.workflow_id}{ID_DELIM}{name}'
                if name in config.taskdefs:
                    families[f_id].child_tasks.append(ch_id)
                else:
                    families[f_id].child_families.append(ch_id)

        # Populate static fields of workflow
        workflow.api_version = API
        workflow.cylc_version = CYLC_VERSION
        workflow.name = self.schd.workflow
        workflow.owner = self.schd.owner
        workflow.host = self.schd.host
        workflow.port = self.schd.port or -1
        workflow.pub_port = self.schd.pub_port or -1
        user_defined_meta = {}
        for key, val in config.cfg['meta'].items():
            if key in ['title', 'description', 'URL']:
                setattr(workflow.meta, key, val)
            else:
                user_defined_meta[key] = val
        workflow.meta.user_defined = json.dumps(user_defined_meta)
        workflow.tree_depth = max([
            len(val)
            for val in config.get_first_parent_ancestors(pruned=True).values()
        ]) - 1

        if get_utc_mode():
            time_zone_info = TIME_ZONE_UTC_INFO
        else:
            time_zone_info = TIME_ZONE_LOCAL_INFO
        for key, val in time_zone_info.items():
            setattr(workflow.time_zone_info, key, val)

        workflow.run_mode = config.run_mode()
        workflow.cycling_mode = config.cfg['scheduling']['cycling mode']
        workflow.workflow_log_dir = self.schd.workflow_log_dir
        workflow.job_log_names.extend(list(JOB_LOG_OPTS.values()))
        workflow.ns_def_order.extend(config.ns_defn_order)

        workflow.broadcasts = json.dumps(self.schd.broadcast_mgr.broadcasts)

        workflow.tasks.extend(list(tasks))
        workflow.families.extend(list(families))

        self.ancestors = ancestors
        self.descendants = descendants
        self.parents = parents

    def increment_graph_window(
            self, itask, edge_distance=0, active_id=None,
            descendant=False, is_parent=False):
        """Generate graph window about given origin to n-edge-distance.

        Args:
            name (str):
                Task name.
            point (cylc.flow.cycling.PointBase):
                PointBase derived object.
            flow_label (str):
                Flow label used to distinguish multiple runs.
            edge_distance (int):
                Graph distance from active/origin node.
            active_id (str):
                Active/origin node id.
            descendant (bool):
                Is the current node a direct descendent of the active/origin.

        Returns:

            None

        """
        # Create this source node
        s_node = f'{itask.tdef.name}.{itask.point}'
        s_id = (
            f'{self.workflow_id}{ID_DELIM}'
            f'{itask.point}{ID_DELIM}{itask.tdef.name}'
        )
        if active_id is None:
            active_id = s_id

        # Setup and check if active node is another's boundary node
        # to flag its paths for pruning.
        if edge_distance == 0:
            self.n_window_edges[active_id] = set()
            self.n_window_boundary_nodes[active_id] = {}
            self.n_window_nodes[active_id] = set()
            if active_id in self.prune_trigger_nodes:
                self.prune_flagged_nodes.update(
                    self.prune_trigger_nodes[active_id])
                del self.prune_trigger_nodes[active_id]

        # This part is vital to constructing a set of boundary nodes
        # associated with the current Active node.
        if edge_distance > self.n_edge_distance:
            if descendant and self.n_edge_distance > 0:
                self.n_window_boundary_nodes[
                    active_id].setdefault(edge_distance, set()).add(s_id)
            return
        if (
                (not any(itask.graph_children.values()) and descendant)
                or self.n_edge_distance == 0
        ):
            self.n_window_boundary_nodes[
                active_id].setdefault(edge_distance, set()).add(s_id)

        self.n_window_nodes[active_id].add(s_id)
        # Generate task proxy node
        self.generate_ghost_task(s_id, itask, is_parent)

        edge_distance += 1

        # TODO: xtrigger is workflow_state edges too
        # Reference set for workflow relations
        for items in itask.graph_children.values():
            if edge_distance == 1:
                descendant = True
            self._expand_graph_window(
                s_id, s_node, items, active_id, itask.flow_label, itask.reflow,
                edge_distance, descendant, False)

        for items in generate_graph_parents(itask.tdef, itask.point).values():
            self._expand_graph_window(
                s_id, s_node, items, active_id, itask.flow_label, itask.reflow,
                edge_distance, False, True)

        if edge_distance == 1:
            levels = self.n_window_boundary_nodes[active_id].keys()
            # Could be self-reference node foo:failed => foo
            if not levels:
                self.n_window_boundary_nodes[active_id][0] = {active_id}
                levels = (0,)
            # Only trigger pruning for furthest set of boundary nodes
            for tp_id in self.n_window_boundary_nodes[active_id][max(levels)]:
                self.prune_trigger_nodes.setdefault(
                    tp_id, set()).add(active_id)
            del self.n_window_boundary_nodes[active_id]
            if self.n_window_edges[active_id]:
                getattr(self.updated[WORKFLOW], EDGES).edges.extend(
                    self.n_window_edges[active_id])

    def _expand_graph_window(
            self, s_id, s_node, items, active_id, flow_label, reflow,
            edge_distance, descendant=False, is_parent=False):
        """Construct nodes/edges for children/parents of source node."""
        for t_name, t_point, _ in items:
            t_node = f'{t_name}.{t_point}'
            t_id = (
                f'{self.workflow_id}{ID_DELIM}{t_point}{ID_DELIM}{t_name}')
            # Initiate edge element.
            if is_parent:
                e_id = (
                    f'{self.workflow_id}{ID_DELIM}{t_node}{ID_DELIM}{s_node}')
            else:
                e_id = (
                    f'{self.workflow_id}{ID_DELIM}{s_node}{ID_DELIM}{t_node}')
            if e_id in self.n_window_edges[active_id]:
                continue
            if (
                e_id not in self.data[self.workflow_id][EDGES]
                and e_id not in self.added[EDGES]
                and edge_distance <= self.n_edge_distance
            ):
                self.added[EDGES][e_id] = PbEdge(
                    id=e_id,
                    source=s_id,
                    target=t_id
                )
                # Add edge id to node field for resolver reference
                self.updated[TASK_PROXIES].setdefault(
                    t_id,
                    PbTaskProxy(id=t_id)).edges.append(e_id)
                self.updated[TASK_PROXIES].setdefault(
                    s_id,
                    PbTaskProxy(id=s_id)).edges.append(e_id)
                self.n_window_edges[active_id].add(e_id)
            if t_id in self.n_window_nodes[active_id]:
                continue
            self.increment_graph_window(
                TaskProxy(
                    self.schd.config.get_taskdef(t_name),
                    t_point, flow_label,
                    submit_num=0, reflow=reflow),
                edge_distance, active_id, descendant, is_parent)

    def remove_pool_node(self, name, point):
        """Remove ID reference and flag isolate node/branch for pruning."""
        tp_id = f'{self.workflow_id}{ID_DELIM}{point}{ID_DELIM}{name}'
        if tp_id in self.all_task_pool:
            self.all_task_pool.remove(tp_id)
        # flagged isolates/end-of-branch nodes for pruning on removal
        if (
                tp_id in self.prune_trigger_nodes and
                tp_id in self.prune_trigger_nodes[tp_id]
        ):
            self.prune_flagged_nodes.update(self.prune_trigger_nodes[tp_id])
            del self.prune_trigger_nodes[tp_id]

    def add_pool_node(self, name, point):
        """Add external ID reference for internal task pool node."""
        tp_id = f'{self.workflow_id}{ID_DELIM}{point}{ID_DELIM}{name}'
        self.all_task_pool.add(tp_id)

    def generate_ghost_task(self, tp_id, itask, is_parent=False):
        """Create task-point element populated with static data.

        Args:
            tp_id (str):
                data-store task proxy ID.
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy object.
            is_parent (bool):
                Used to determine whether to load DB state.

        Returns:

            None

        """
        t_id = f'{self.workflow_id}{ID_DELIM}{itask.tdef.name}'
        point_string = f'{itask.point}'
        task_proxies = self.data[self.workflow_id][TASK_PROXIES]
        if tp_id in task_proxies or tp_id in self.added[TASK_PROXIES]:
            return

        # Most the time the definition node will be in the store,
        # so use try/except.
        try:
            task_def = self.data[self.workflow_id][TASKS][t_id]
        except KeyError:
            task_def = self.added[TASKS][t_id]

        update_time = time()
        tp_stamp = f'{tp_id}@{update_time}'
        tproxy = PbTaskProxy(
            stamp=tp_stamp,
            id=tp_id,
            task=t_id,
            cycle_point=point_string,
            depth=task_def.depth,
            name=task_def.name,
            state=TASK_STATUS_WAITING,
            flow_label=itask.flow_label
        )
        if is_parent and tp_id not in self.n_window_nodes:
            # TODO: Load task info from DB, including itask prerequisites
            tproxy.state = TASK_STATUS_EXPIRED
        else:
            tproxy.state = TASK_STATUS_WAITING
            tproxy.reflow = itask.reflow

        tproxy.namespace[:] = task_def.namespace
        tproxy.ancestors[:] = [
            f'{self.workflow_id}{ID_DELIM}{point_string}{ID_DELIM}{a_name}'
            for a_name in self.ancestors[task_def.name]
            if a_name != task_def.name]
        tproxy.first_parent = tproxy.ancestors[0]

        for prereq in itask.state.prerequisites:
            # Protobuf messages populated within
            prereq_obj = prereq.api_dump(self.workflow_id)
            if prereq_obj:
                tproxy.prerequisites.append(prereq_obj)

        for label, message, satisfied in itask.state.outputs.get_all():
            output = tproxy.outputs[label]
            output.label = label
            output.message = message
            output.satisfied = satisfied
            output.time = update_time

        if itask.tdef.clocktrigger_offset is not None:
            tproxy.clock_trigger.satisfied = itask.is_waiting_clock_done()
            tproxy.clock_trigger.time = itask.clock_trigger_time
            tproxy.clock_trigger.time_string = time2str(
                itask.clock_trigger_time)

        for trig, satisfied in itask.state.external_triggers.items():
            ext_trig = tproxy.external_triggers[trig]
            ext_trig.id = trig
            ext_trig.satisfied = satisfied

        for label, satisfied in itask.state.xtriggers.items():
            sig = self.schd.xtrigger_mgr.get_xtrig_ctx(
                itask, label).get_signature()
            xtrig = tproxy.xtriggers[sig]
            xtrig.id = sig
            xtrig.label = label
            xtrig.satisfied = satisfied
            self.xtrigger_tasks.setdefault(sig, set()).add(tp_id)

        self.added[TASK_PROXIES][tp_id] = tproxy
        getattr(self.updated[WORKFLOW], TASK_PROXIES).append(tp_id)
        self.updated[TASKS].setdefault(
            t_id,
            PbTask(
                stamp=f'{t_id}@{update_time}',
                id=t_id,
            )
        ).proxies.append(tp_id)
        self.generate_ghost_family(tproxy.first_parent, child_task=tp_id)
        self.state_update_families.add(tproxy.first_parent)
        if tproxy.state in self.latest_state_tasks:
            tp_ref = f'{tproxy.name}.{tproxy.cycle_point}'
            tp_queue = self.latest_state_tasks[tproxy.state]
            if tp_ref in tp_queue:
                tp_queue.remove(tp_ref)
            self.latest_state_tasks[tproxy.state].appendleft(tp_ref)
        self.updates_pending = True

    def generate_ghost_family(self, fp_id, child_fam=None, child_task=None):
        """Generate the family-point elements from given ID if non-existent.

        Adds the ID of the child proxy that called for it's creation. Also
        generates parents recursively to root if they don't exist.

        Args:
            fp_id (str):
                Family proxy ID
            child_fam (str):
                Family proxy ID
            child_task (str):
                Task proxy ID

        Returns:

            None

        """

        update_time = time()
        families = self.data[self.workflow_id][FAMILIES]
        if not families:
            families = self.added[FAMILIES]
        fp_data = self.data[self.workflow_id][FAMILY_PROXIES]
        fp_added = self.added[FAMILY_PROXIES]
        fp_updated = self.updated[FAMILY_PROXIES]
        if fp_id in fp_data:
            fp_delta = fp_data[fp_id]
            fp_parent = fp_updated.setdefault(fp_id, PbFamilyProxy(id=fp_id))
        elif fp_id in fp_added:
            fp_delta = fp_added[fp_id]
            fp_parent = fp_added.setdefault(fp_id, PbFamilyProxy(id=fp_id))
        else:
            _, _, point_string, name = fp_id.split(ID_DELIM)
            fam = families[f'{self.workflow_id}{ID_DELIM}{name}']
            fp_delta = PbFamilyProxy(
                stamp=f'{fp_id}@{update_time}',
                id=fp_id,
                cycle_point=point_string,
                name=fam.name,
                family=fam.id,
                depth=fam.depth,
            )
            fp_delta.ancestors[:] = [
                f'{self.workflow_id}{ID_DELIM}{point_string}{ID_DELIM}{a_name}'
                for a_name in self.ancestors[fam.name]
                if a_name != fam.name]
            if fp_delta.ancestors:
                fp_delta.first_parent = fp_delta.ancestors[0]
            self.added[FAMILY_PROXIES][fp_id] = fp_delta
            fp_parent = fp_delta
            # Add ref ID to family element
            f_delta = PbFamily(id=fam.id, stamp=f'{fam.id}@{update_time}')
            f_delta.proxies.append(fp_id)
            self.updated[FAMILIES].setdefault(
                fam.id, PbFamily(id=fam.id)).MergeFrom(f_delta)
            # Add ref ID to workflow element
            getattr(self.updated[WORKFLOW], FAMILY_PROXIES).append(fp_id)
            # Generate this families parent if it not root.
            if fp_delta.first_parent:
                self.generate_ghost_family(
                    fp_delta.first_parent, child_fam=fp_id)
        if child_fam is None:
            fp_parent.child_tasks.append(child_task)
        elif child_fam not in fp_parent.child_families:
            fp_parent.child_families.append(child_fam)

    def insert_job(self, name, point_string, job_conf):
        """Insert job into data-store.

        Args:
            name (str): Corresponding task name.
            point_string (str): Cycle point string
            job_conf (dic):
                Dictionary of job configuration used to generate
                the job script.
                (see TaskJobManager._prep_submit_task_job_impl)

        Returns:

            None

        """
        sub_num = job_conf['submit_num']
        tp_id, tproxy = self.store_node_fetcher(name, point_string)
        if not tproxy:
            return
        update_time = time()
        j_id = f'{tp_id}{ID_DELIM}{sub_num}'
        j_buf = PbJob(
            stamp=f'{j_id}@{update_time}',
            id=j_id,
            submit_num=sub_num,
            state=JOB_STATUSES_ALL[0],
            task_proxy=tp_id,
            job_runner_name=job_conf['job_runner_name'],
            env_script=job_conf['env-script'],
            err_script=job_conf['err-script'],
            exit_script=job_conf['exit-script'],
            execution_time_limit=job_conf['execution_time_limit'],
            platform=job_conf['platform']['name'],
            init_script=job_conf['init-script'],
            post_script=job_conf['post-script'],
            pre_script=job_conf['pre-script'],
            script=job_conf['script'],
            work_sub_dir=job_conf['work_d'],
            name=tproxy.name,
            cycle_point=tproxy.cycle_point,
            directives=json.dumps(job_conf['directives']),
            environment=json.dumps(job_conf['environment']),
            param_var=json.dumps(job_conf['param_var'])
        )

        # Add in log files.
        j_buf.job_log_dir = get_task_job_log(
            self.schd.workflow, tproxy.cycle_point, tproxy.name, sub_num)
        j_buf.extra_logs.extend(job_conf['logfiles'])

        self.added[JOBS][j_id] = j_buf
        getattr(self.updated[WORKFLOW], JOBS).append(j_id)
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id,
            PbTaskProxy(
                stamp=f'{tp_id}@{update_time}',
                id=tp_id,
            )
        )
        tp_delta.job_submits = sub_num
        tp_delta.jobs.append(j_id)
        self.updates_pending = True

    def insert_db_job(self, row_idx, row):
        """Load job element from DB post restart."""
        if row_idx == 0:
            LOG.info("LOADING job data")
        (point_string, name, status, submit_num, time_submit, time_run,
         time_run_exit, job_runner_name, job_id, platform_name) = row
        if status not in JOB_STATUS_SET:
            return
        tp_id, tproxy = self.store_node_fetcher(name, point_string)
        if not tproxy:
            return
        j_id = f'{tp_id}{ID_DELIM}{submit_num}'
        try:
            update_time = time()
            j_buf = PbJob(
                stamp=f'{j_id}@{update_time}',
                id=j_id,
                submit_num=submit_num,
                state=status,
                task_proxy=tp_id,
                submitted_time=time_submit,
                started_time=time_run,
                finished_time=time_run_exit,
                job_runner_name=job_runner_name,
                job_id=job_id,
                platform=platform_name,
                name=name,
                cycle_point=tproxy.cycle_point,
            )
            # Add in log files.
            j_buf.job_log_dir = get_task_job_log(
                self.schd.workflow, point_string, name, submit_num)
        except WorkflowConfigError:
            LOG.exception((
                'ignoring job %s from the workflow run database\n'
                '(its task definition has probably been deleted).'
            ) % j_id)
        except Exception:
            LOG.exception('could not load job %s' % j_id)
        else:
            self.added[JOBS][j_id] = j_buf
            getattr(self.updated[WORKFLOW], JOBS).append(j_id)
            tp_delta = self.updated[TASK_PROXIES].setdefault(
                tp_id,
                PbTaskProxy(
                    stamp=f'{tp_id}@{update_time}',
                    id=tp_id,
                )
            )
            tp_delta.job_submits = max((submit_num, tp_delta.job_submits))
            tp_delta.jobs.append(j_id)
            self.updates_pending = True

    def update_data_structure(self):
        """Workflow batch updates in the data structure."""

        # Avoids changing window edge distance during edge/node creation
        if self.next_n_edge_distance is not None:
            self.n_edge_distance = self.next_n_edge_distance
            self.next_n_edge_distance = None

        self.prune_data_store()
        if self.state_update_families:
            self.update_family_proxies()

        if self.updates_pending:
            # Update workflow statuses and totals if needed
            self.update_workflow()
            self.updates_pending = False

            # Apply current deltas
            self.apply_deltas()
            # Gather this batch of deltas for publish
            self.publish_deltas = self.get_publish_deltas()
            # Clear deltas
            self.clear_deltas()

    def prune_data_store(self):
        """Remove flagged nodes and edges not in the set of active paths."""

        self.family_pruned_ids.clear()

        if not self.prune_flagged_nodes:
            return

        in_paths_nodes = set().union(*[
            v
            for k, v in self.n_window_nodes.items()
            if k in self.all_task_pool
        ])
        out_paths_nodes = self.prune_flagged_nodes.union(*[
            v
            for k, v in self.n_window_nodes.items()
            if k in self.prune_flagged_nodes
        ])
        # Trim out any nodes in the runahead pool
        out_paths_nodes.difference(self.all_task_pool)
        # Prune only nodes not in the paths of active nodes
        node_ids = out_paths_nodes.difference(in_paths_nodes)
        # Absolute triggers may be present in task pool, so recheck.
        # Clear the rest.
        self.prune_flagged_nodes.intersection_update(self.all_task_pool)

        tp_data = self.data[self.workflow_id][TASK_PROXIES]
        tp_added = self.added[TASK_PROXIES]
        parent_ids = set()
        for tp_id in list(node_ids):
            if tp_id in self.n_window_nodes:
                del self.n_window_nodes[tp_id]
            if tp_id in self.n_window_edges:
                del self.n_window_edges[tp_id]
            if tp_id in tp_data:
                node = tp_data[tp_id]
            elif tp_id in tp_added:
                node = tp_added[tp_id]
            else:
                node_ids.remove(tp_id)
                continue
            for sig in node.xtriggers:
                self.xtrigger_tasks[sig].remove(tp_id)
                if not self.xtrigger_tasks[sig]:
                    del self.xtrigger_tasks[sig]
            self.deltas[TASK_PROXIES].pruned.append(tp_id)
            self.deltas[JOBS].pruned.extend(node.jobs)
            self.deltas[EDGES].pruned.extend(node.edges)
            parent_ids.add(node.first_parent)

        checked_ids = set()
        while parent_ids:
            self._family_ascent_point_prune(
                next(iter(parent_ids)),
                node_ids, parent_ids, checked_ids, self.family_pruned_ids)
        if self.family_pruned_ids:
            self.deltas[FAMILY_PROXIES].pruned.extend(self.family_pruned_ids)
        if node_ids:
            self.updates_pending = True

    def _family_ascent_point_prune(
            self, fp_id, node_ids, parent_ids, checked_ids, prune_ids):
        """Find and prune family recursively checking child families.

        Recursively map out child families to the bottom from the origin
        family. The work back up to origin checking these families are active.

        """
        fp_data = self.data[self.workflow_id][FAMILY_PROXIES]
        fp_updated = self.updated[FAMILY_PROXIES]
        if fp_id in fp_data:
            fam_node = fp_data[fp_id]
            # Gather child families, then check/update recursively
            child_fam_nodes = [
                n_id
                for n_id in fam_node.child_families
                if n_id not in checked_ids
            ]
            for child_id in child_fam_nodes:
                self._family_ascent_point_prune(
                    child_id, node_ids, parent_ids, checked_ids, prune_ids)
            child_tasks = set(fam_node.child_tasks)
            child_families = set(fam_node.child_families)
            # Add in any new children
            if fp_id in fp_updated:
                if fp_updated[fp_id].child_tasks:
                    child_tasks.update(fp_updated[fp_id].child_tasks)
                if fp_updated[fp_id].child_families:
                    child_families.update(fp_updated[fp_id].child_families)
            # if any child tasks or families are active, don't prune.
            if (
                    child_tasks.difference(node_ids)
                    or child_families.difference(prune_ids)
            ):
                if fp_id in prune_ids:
                    self.state_update_families.add(fp_id)
            else:
                if fam_node.first_parent:
                    parent_ids.add(fam_node.first_parent)
                prune_ids.add(fp_id)
        checked_ids.add(fp_id)
        if fp_id in parent_ids:
            parent_ids.remove(fp_id)

    def update_family_proxies(self):
        """Update state & summary of flagged families and ancestors.

        Tasks whose state are updated flag their first parent, as a family
        to be updated, by adding their ID to a set.
        This set is iterated over here until empty, with each members child
        families checked/updated and first parent added to the set (flagged).
        Order doesn't matter, as every family will be checked/updated once at
        most (as an ancestor will-be/has-been added to the set of updated
        families).

        """
        self.updated_state_families.clear()
        while self.state_update_families:
            self._family_ascent_point_update(
                next(iter(self.state_update_families)))
        if self.updated_state_families:
            self.updates_pending = True

    def _family_ascent_point_update(self, fp_id):
        """Updates the given family and children recursively.

        First the child families that haven't been checked/updated are acted
        on first by calling this function. This recursion ends at the family
        first called with this function, which then adds it's first parent
        ancestor to the set of families flagged for update.

        """
        fp_added = self.added[FAMILY_PROXIES]
        fp_data = self.data[self.workflow_id][FAMILY_PROXIES]
        if fp_id in fp_data:
            fam_node = fp_data[fp_id]
        elif fp_id in fp_added:
            fam_node = fp_added[fp_id]
        else:
            # TODO: Shouldn't need with event driven updates
            # as nodes will be updated before removal.
            if fp_id in self.state_update_families:
                self.updated_state_families.add(fp_id)
                self.state_update_families.remove(fp_id)
            return
        # Gather child families, then check/update recursively
        child_fam_nodes = [
            n_id
            for n_id in fam_node.child_families
            if n_id not in self.updated_state_families
        ]
        for child_fam_id in child_fam_nodes:
            self._family_ascent_point_update(child_fam_id)
        if fp_id in self.state_update_families:
            fp_updated = self.updated[FAMILY_PROXIES]
            tp_data = self.data[self.workflow_id][TASK_PROXIES]
            tp_updated = self.updated[TASK_PROXIES]
            tp_added = self.added[TASK_PROXIES]
            # Count child family states, set is_held, is_queued, is_runahead
            state_counter = Counter({})
            is_held_total = 0
            is_queued_total = 0
            is_runahead_total = 0
            for child_id in fam_node.child_families:
                child_node = fp_updated.get(child_id, fp_data.get(child_id))
                if child_node is not None:
                    is_held_total += child_node.is_held_total
                    is_queued_total += child_node.is_queued_total
                    is_runahead_total += child_node.is_runahead_total
                    state_counter += Counter(dict(child_node.state_totals))
            # Gather all child task states
            task_states = []
            for tp_id in fam_node.child_tasks:

                tp_delta = tp_updated.get(tp_id)
                tp_node = tp_added.get(tp_id, tp_data.get(tp_id))

                tp_state = tp_delta
                if tp_state is None or not tp_state.HasField('state'):
                    tp_state = tp_node
                if tp_state.state:
                    task_states.append(tp_state.state)

                tp_held = tp_delta
                if tp_held is None or not tp_held.HasField('is_held'):
                    tp_held = tp_node
                if tp_held.is_held:
                    is_held_total += 1

                tp_queued = tp_delta
                if tp_queued is None or not tp_queued.HasField('is_queued'):
                    tp_queued = tp_node
                if tp_queued.is_queued:
                    is_queued_total += 1

                tp_runahead = tp_delta
                if (tp_runahead is None
                        or not tp_runahead.HasField('is_runahead')):
                    tp_runahead = tp_node
                if tp_runahead.is_runahead:
                    is_runahead_total += 1

            state_counter += Counter(task_states)
            # created delta data element
            fp_delta = PbFamilyProxy(
                id=fp_id,
                stamp=f'{fp_id}@{time()}',
                state=extract_group_state(state_counter.keys()),
                is_held=(is_held_total > 0),
                is_held_total=is_held_total,
                is_queued=(is_queued_total > 0),
                is_queued_total=is_queued_total,
                is_runahead=(is_runahead_total > 0),
                is_runahead_total=is_runahead_total
            )
            fp_delta.states[:] = state_counter.keys()
            # Use all states to clean up pruned counts
            for state in TASK_STATUSES_ORDERED:
                fp_delta.state_totals[state] = state_counter.get(state, 0)
            fp_updated.setdefault(fp_id, PbFamilyProxy()).MergeFrom(fp_delta)
            # mark as updated in case parent family is updated next
            self.updated_state_families.add(fp_id)
            # mark parent for update
            if fam_node.first_parent:
                self.state_update_families.add(fam_node.first_parent)
            self.state_update_families.remove(fp_id)

    def set_graph_window_extent(self, n_edge_distance):
        """Set what the max edge distance will change to.

        Args:
            n_edge_distance (int):
                Maximum edge distance from active node.

        """
        self.next_n_edge_distance = n_edge_distance
        self.updates_pending = True

    def update_workflow(self):
        """Update workflow element status and state totals."""
        # Create new message and copy existing message content
        data = self.data[self.workflow_id]
        w_data = data[WORKFLOW]
        w_delta = self.updated[WORKFLOW]
        delta_set = False

        # new updates/deltas not applied yet
        # so need to search/use updated states if available.
        if self.updated_state_families:
            state_counter = Counter({})
            is_held_total = 0
            is_queued_total = 0
            is_runahead_total = 0
            for root_id in set(
                    [n.id
                     for n in data[FAMILY_PROXIES].values()
                     if n.name == 'root'] +
                    [n.id
                     for n in self.added[FAMILY_PROXIES].values()
                     if n.name == 'root']
            ):
                root_node_updated = self.updated[FAMILY_PROXIES].get(root_id)
                if root_node_updated is not None and root_node_updated.state:
                    root_node = root_node_updated
                else:
                    root_node = data[FAMILY_PROXIES].get(root_id)
                if root_node is not None:
                    is_held_total += root_node.is_held_total
                    is_queued_total += root_node.is_queued_total
                    is_runahead_total += root_node.is_runahead_total
                    state_counter += Counter(dict(root_node.state_totals))
            w_delta.states[:] = state_counter.keys()
            for state, state_cnt in state_counter.items():
                w_delta.state_totals[state] = state_cnt

            w_delta.is_held_total = is_held_total
            w_delta.is_queued_total = is_queued_total
            w_delta.is_runahead_total = is_runahead_total
            delta_set = True

            for state, tp_queue in self.latest_state_tasks.items():
                w_delta.latest_state_tasks[state].task_proxies[:] = tp_queue

        # Set status & msg if changed.
        status, status_msg = map(
            str, get_workflow_status(self.schd))
        if w_data.status != status or w_data.status_msg != status_msg:
            w_delta.status = status
            w_delta.status_msg = status_msg
            delta_set = True

        if self.schd.pool.main_pool:
            pool_points = set(self.schd.pool.main_pool)
            oldest_point = str(min(pool_points))
            if w_data.oldest_active_cycle_point != oldest_point:
                w_delta.oldest_active_cycle_point = oldest_point
                delta_set = True
            newest_point = str(max(pool_points))
            if w_data.newest_active_cycle_point != newest_point:
                w_delta.newest_active_cycle_point = newest_point
                delta_set = True

        if delta_set:
            w_delta.id = self.workflow_id
            w_delta.last_updated = time()
            w_delta.stamp = f'{w_delta.id}@{w_delta.last_updated}'

    def delta_workflow_ports(self):
        """Set or update the workflow comms ports."""
        w_delta = self.updated[WORKFLOW]
        w_delta.id = self.workflow_id
        w_delta.last_updated = time()
        w_delta.stamp = f'{w_delta.id}@{w_delta.last_updated}'

        w_delta.port = self.schd.port
        w_delta.pub_port = self.schd.pub_port
        self.updates_pending = True

    def delta_broadcast(self):
        """Collects broadcasts on change event."""
        w_delta = self.updated[WORKFLOW]
        w_delta.id = self.workflow_id
        w_delta.last_updated = time()
        w_delta.stamp = f'{w_delta.id}@{w_delta.last_updated}'

        w_delta.broadcasts = json.dumps(self.schd.broadcast_mgr.broadcasts)
        self.updates_pending = True

    # -----------
    # Task Deltas
    # -----------
    def delta_task_state(self, itask):
        """Create delta for change in task proxy state.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tp_id, tproxy = self.store_node_fetcher(itask.tdef.name, itask.point)
        if not tproxy:
            return
        update_time = time()

        # update task instance
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        tp_delta.state = itask.state.status
        self.state_update_families.add(tproxy.first_parent)
        if tp_delta.state in self.latest_state_tasks:
            tp_ref = f'{tproxy.name}.{tproxy.cycle_point}'
            tp_queue = self.latest_state_tasks[tp_delta.state]
            if tp_ref in tp_queue:
                tp_queue.remove(tp_ref)
            self.latest_state_tasks[tp_delta.state].appendleft(tp_ref)
        # if state is final work out new task mean.
        if tp_delta.state in TASK_STATUSES_FINAL:
            elapsed_time = task_mean_elapsed_time(itask.tdef)
            if elapsed_time:
                t_id = f'{self.workflow_id}{ID_DELIM}{tproxy.name}'
                t_delta = PbTask(
                    stamp=f'{t_id}@{update_time}',
                    mean_elapsed_time=elapsed_time
                )
                self.updated[TASKS].setdefault(
                    t_id,
                    PbTask(id=t_id)).MergeFrom(t_delta)
        self.updates_pending = True

    def delta_task_held(self, itask):
        """Create delta for change in task proxy held state.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tp_id, tproxy = self.store_node_fetcher(itask.tdef.name, itask.point)
        if not tproxy:
            return
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{time()}'
        tp_delta.is_held = itask.state.is_held
        self.state_update_families.add(tproxy.first_parent)
        self.updates_pending = True

    def delta_task_queued(self, itask):
        """Create delta for change in task proxy queued state.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tp_id, tproxy = self.store_node_fetcher(itask.tdef.name, itask.point)
        if not tproxy:
            return
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{time()}'
        tp_delta.is_queued = itask.state.is_queued
        self.state_update_families.add(tproxy.first_parent)
        self.updates_pending = True

    def delta_task_runahead(self, itask):
        """Create delta for change in task proxy runahead state.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tp_id, tproxy = self.store_node_fetcher(itask.tdef.name, itask.point)
        if not tproxy:
            return
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{time()}'
        tp_delta.is_runahead = itask.state.is_runahead
        self.state_update_families.add(tproxy.first_parent)
        self.updates_pending = True

    def delta_task_output(self, itask, message):
        """Create delta for change in task proxy output.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tp_id, tproxy = self.store_node_fetcher(itask.tdef.name, itask.point)
        if not tproxy:
            return
        item = itask.state.outputs.get_item(message)
        if item is None:
            return
        label, _, satisfied = item
        # update task instance
        update_time = time()
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        tp_delta.latest_message = message
        output = tp_delta.outputs[label]
        output.label = label
        output.message = message
        output.satisfied = satisfied
        output.time = update_time
        self.updates_pending = True

    def delta_task_outputs(self, itask):
        """Create delta for change in all task proxy outputs.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tp_id, tproxy = self.store_node_fetcher(itask.tdef.name, itask.point)
        if not tproxy:
            return
        update_time = time()
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        for label, _, satisfied in itask.state.outputs.get_all():
            output = tp_delta.outputs[label]
            output.label = label
            output.satisfied = satisfied
            output.time = update_time

        self.updates_pending = True

    def delta_task_prerequisite(self, itask):
        """Create delta for change in task proxy prerequisite.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.

        """
        tp_id, tproxy = self.store_node_fetcher(itask.tdef.name, itask.point)
        if not tproxy:
            return
        update_time = time()

        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        prereq_list = []
        for prereq in itask.state.prerequisites:
            # Protobuf messages populated within
            prereq_obj = prereq.api_dump(self.workflow_id)
            if prereq_obj:
                prereq_list.append(prereq_obj)
        del tp_delta.prerequisites[:]
        tp_delta.prerequisites.extend(prereq_list)
        self.updates_pending = True

    def delta_task_clock_trigger(self, itask, check_items):
        """Create delta for change in task proxy prereqs.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.
            check_items (tuple):
                Collection of prerequisites checked to determine if
                task is ready to run.

        """
        tp_id, tproxy = self.store_node_fetcher(itask.tdef.name, itask.point)
        if not tproxy:
            return
        if len(check_items) == 1:
            return
        _, clock, _ = check_items
        # update task instance
        if (
                tproxy.HasField('clock_trigger')
                and tproxy.clock_trigger.satisfied is not clock
        ):
            update_time = time()
            tp_delta = self.updated[TASK_PROXIES].setdefault(
                tp_id, PbTaskProxy(id=tp_id))
            tp_delta.stamp = f'{tp_id}@{update_time}'
            tp_delta.clock_trigger.satisfied = clock
            self.updates_pending = True

    def delta_task_ext_trigger(self, itask, trig, message, satisfied):
        """Create delta for change in task proxy external_trigger.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.
            trig (str): Trigger ID.
            message (str): Trigger message.

        """
        tp_id, tproxy = self.store_node_fetcher(itask.tdef.name, itask.point)
        if not tproxy:
            return
        # update task instance
        update_time = time()
        tp_delta = self.updated[TASK_PROXIES].setdefault(
            tp_id, PbTaskProxy(id=tp_id))
        tp_delta.stamp = f'{tp_id}@{update_time}'
        ext_trigger = tp_delta.external_triggers[trig]
        ext_trigger.message = message
        ext_trigger.satisfied = True
        ext_trigger.time = update_time
        self.updates_pending = True

    def delta_task_xtrigger(self, sig, satisfied):
        """Create delta for change in task proxy xtrigger.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                Update task-node from corresponding task proxy
                objects from the workflow task pool.
            sig (str): Context of function call (name, args).
            satisfied (bool): Trigger message.

        """
        update_time = time()
        for tp_id in self.xtrigger_tasks.get(sig, set()):
            # update task instance
            tp_delta = self.updated[TASK_PROXIES].setdefault(
                tp_id, PbTaskProxy(id=tp_id))
            tp_delta.stamp = f'{tp_id}@{update_time}'
            xtrigger = tp_delta.xtriggers[sig]
            xtrigger.satisfied = satisfied
            xtrigger.time = update_time
            self.updates_pending = True

    # -----------
    # Job Deltas
    # -----------
    def delta_job_msg(self, job_d, msg):
        """Add message to job."""
        point, name, sub_num = parse_job_item(job_d)
        j_id, job = self.store_node_fetcher(name, point, sub_num)
        if not job:
            return
        j_delta = PbJob(stamp=f'{j_id}@{time()}')
        j_delta.messages.append(msg)
        self.updated[JOBS].setdefault(
            j_id,
            PbJob(id=j_id)
        ).MergeFrom(j_delta)
        self.updates_pending = True

    def delta_job_attr(self, job_d, attr_key, attr_val):
        """Set job attribute."""
        point, name, sub_num = parse_job_item(job_d)
        j_id, job = self.store_node_fetcher(name, point, sub_num)
        if not job:
            return
        j_delta = PbJob(stamp=f'{j_id}@{time()}')
        setattr(j_delta, attr_key, attr_val)
        self.updated[JOBS].setdefault(
            j_id,
            PbJob(id=j_id)
        ).MergeFrom(j_delta)
        self.updates_pending = True

    def delta_job_state(self, job_d, status):
        """Set job state."""
        point, name, sub_num = parse_job_item(job_d)
        j_id, job = self.store_node_fetcher(name, point, sub_num)
        if not job or status not in JOB_STATUS_SET:
            return
        j_delta = PbJob(
            stamp=f'{j_id}@{time()}',
            state=status
        )
        self.updated[JOBS].setdefault(
            j_id,
            PbJob(id=j_id)
        ).MergeFrom(j_delta)
        self.updates_pending = True

    def delta_job_time(self, job_d, event_key, time_str=None):
        """Set an event time in job pool object.

        Set values of both event_key + '_time' and event_key + '_time_string'.
        """
        point, name, sub_num = parse_job_item(job_d)
        j_id, job = self.store_node_fetcher(name, point, sub_num)
        if not job:
            return
        j_delta = PbJob(stamp=f'{j_id}@{time()}')
        time_attr = f'{event_key}_time'
        setattr(j_delta, time_attr, time_str)
        self.updated[JOBS].setdefault(
            j_id,
            PbJob(id=j_id)
        ).MergeFrom(j_delta)
        self.updates_pending = True

    def store_node_fetcher(
            self, name, point=None, sub_num=None, node_type=TASK_PROXIES):
        """Check that task proxy is in or being added to the store"""
        if point is None:
            node_id = f'{self.workflow_id}{ID_DELIM}{name}'
            node_type = TASKS
        elif sub_num is None:
            node_id = f'{self.workflow_id}{ID_DELIM}{point}{ID_DELIM}{name}'
        else:
            node_id = (
                f'{self.workflow_id}{ID_DELIM}{point}'
                f'{ID_DELIM}{name}{ID_DELIM}{sub_num}'
            )
            node_type = JOBS
        if node_id in self.data[self.workflow_id][node_type]:
            return (node_id, self.data[self.workflow_id][node_type][node_id])
        elif node_id in self.added[node_type]:
            return (node_id, self.added[node_type][node_id])
        return (node_id, False)

    def apply_deltas(self, reloaded=False):
        """Gather and apply deltas."""
        # Gather cumulative update element
        for key, elements in self.added.items():
            if elements:
                if key == WORKFLOW:
                    if elements.ListFields():
                        self.deltas[WORKFLOW].added.CopyFrom(elements)
                    continue
                self.deltas[key].added.extend(elements.values())
        for key, elements in self.updated.items():
            if elements:
                if key == WORKFLOW:
                    if elements.ListFields():
                        self.deltas[WORKFLOW].updated.CopyFrom(elements)
                    continue
                self.deltas[key].updated.extend(elements.values())

        # Apply deltas to local data-store
        data = self.data[self.workflow_id]
        for key, delta in self.deltas.items():
            if delta.ListFields():
                delta.reloaded = reloaded
                apply_delta(key, delta, data)

        # Construct checksum on deltas for export
        update_time = time()
        for key, delta in self.deltas.items():
            if delta.ListFields():
                delta.time = update_time
                if hasattr(delta, 'checksum'):
                    if key == EDGES:
                        s_att = 'id'
                    else:
                        s_att = 'stamp'
                    delta.checksum = generate_checksum(
                        [getattr(e, s_att)
                         for e in data[key].values()]
                    )

    def clear_deltas(self):
        """Clear current deltas."""
        for key in self.deltas:
            self.deltas[key].Clear()
            if key == WORKFLOW:
                self.added[key].Clear()
                self.updated[key].Clear()
                continue
            self.added[key].clear()
            self.updated[key].clear()

    # Message collation and dissemination methods:
    def get_entire_workflow(self):
        """Gather data elements into single Protobuf message.

        Returns:
            cylc.flow.data_messages_pb2.PbEntireWorkflow

        """

        data = self.data[self.workflow_id]

        workflow_msg = PbEntireWorkflow()
        workflow_msg.workflow.CopyFrom(data[WORKFLOW])
        workflow_msg.tasks.extend(data[TASKS].values())
        workflow_msg.task_proxies.extend(data[TASK_PROXIES].values())
        workflow_msg.jobs.extend(data[JOBS].values())
        workflow_msg.families.extend(data[FAMILIES].values())
        workflow_msg.family_proxies.extend(data[FAMILY_PROXIES].values())
        workflow_msg.edges.extend(data[EDGES].values())

        return workflow_msg

    def get_publish_deltas(self):
        """Return deltas for publishing."""
        all_deltas = DELTAS_MAP[ALL_DELTAS]()
        result = []
        for key, delta in self.deltas.items():
            if delta.ListFields():
                result.append(
                    (key.encode('utf-8'), delta, 'SerializeToString'))
                getattr(all_deltas, key).CopyFrom(delta)
        result.append(
            (ALL_DELTAS.encode('utf-8'), all_deltas, 'SerializeToString')
        )
        return deepcopy(result)

    def get_data_elements(self, element_type):
        """Get elements of a given type in the form of a delta.

        Args:
            element_type (str):
                Key from DELTAS_MAP dictionary.

        Returns:
            object
                protobuf (DELTAS_MAP[element_type]) message.

        """
        if element_type not in DELTAS_MAP:
            return DELTAS_MAP[WORKFLOW]()
        data = self.data[self.workflow_id]
        pb_msg = DELTAS_MAP[element_type]()
        pb_msg.time = data[WORKFLOW].last_updated
        if element_type == WORKFLOW:
            pb_msg.added.CopyFrom(data[WORKFLOW])
        else:
            pb_msg.added.extend(data[element_type].values())
        return pb_msg

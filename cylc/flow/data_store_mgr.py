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

Updates are triggered by changes in the task pool;
migrations of task instances from runahead to live pool, and
changes in task state (itask.state.is_updated).

Data elements include a "stamp" field, which is a timestamped ID for use
in assessing changes in the data store, for comparisons of a store sync.

Packaging methods are included for dissemination of protobuf messages.

"""

from collections import Counter
from copy import copy, deepcopy
import json
from time import time
import zlib

from cylc.flow import __version__ as CYLC_VERSION, LOG, ID_DELIM
from cylc.flow.data_messages_pb2 import (
    PbEdge, PbEntireWorkflow, PbFamily, PbFamilyProxy, PbJob, PbTask,
    PbTaskProxy, PbWorkflow, AllDeltas, EDeltas, FDeltas, FPDeltas,
    JDeltas, TDeltas, TPDeltas, WDeltas)
from cylc.flow.network import API
from cylc.flow.suite_status import get_suite_status
from cylc.flow.task_id import TaskID
from cylc.flow.task_job_logs import JOB_LOG_OPTS
from cylc.flow.task_state import TASK_STATUS_WAITING, TASK_STATUS_EXPIRED
from cylc.flow.task_state_prop import extract_group_state
from cylc.flow.taskdef import generate_graph_children, generate_graph_parents
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
    TASK_PROXIES: {'prerequisites', 'outputs'},
    WORKFLOW: {'state_totals', 'states'},
}


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
                    # Clear fields that require overwrite with delta
                    if CLEAR_FIELD_MAP[key]:
                        for field, _ in element.ListFields():
                            if field.name in CLEAR_FIELD_MAP[key]:
                                data[key][element.id].ClearField(field.name)
                    data[key][element.id].MergeFrom(element)
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
        # Prune data elements by id
        for del_id in delta.pruned:
            if del_id not in data[key]:
                continue
            if key == TASK_PROXIES:
                data[TASKS][data[key][del_id].task].proxies.remove(del_id)
                try:
                    data[FAMILY_PROXIES][
                        data[key][del_id].first_parent
                    ].child_tasks.remove(del_id)
                except KeyError:
                    pass
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
        delta_store[DELTA_ADDED][WORKFLOW].id = workflow_id
        delta_store[DELTA_UPDATED][WORKFLOW].id = workflow_id
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
                cylc.flow.data_messages_pb2.PbJob by internal ID, managed by
                cylc.flow.job_pool.JobPool
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

    def __init__(self, schd):
        self.schd = schd
        self.workflow_id = f'{self.schd.owner}{ID_DELIM}{self.schd.suite}'
        self.ancestors = {}
        self.descendants = {}
        self.parents = {}
        self.state_update_families = set()
        self.updated_state_families = set()
        self.n_edge_distance = 1
        self.next_n_edge_distance = None
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
        self.updates_pending = False
        self.delta_queues = {self.workflow_id: {}}
        self.publish_deltas = []
        self.all_task_pool = set()
        self.n_window_nodes = {}
        self.n_window_edges = {}
        self.n_window_boundary_nodes = {}
        self.prune_trigger_nodes = {}
        self.prune_flagged_nodes = set()
        self.prune_pending = False

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

        # Tidy and reassign task jobs after reload
        if reloaded:
            new_tasks = set(self.added[TASK_PROXIES])
            job_tasks = set(self.schd.job_pool.task_jobs)
            for tp_id in job_tasks.difference(new_tasks):
                self.schd.job_pool.remove_task_jobs(tp_id)
            for tp_id, tp_delta in self.added[TASK_PROXIES].items():
                tp_delta.jobs[:] = [
                    j_id
                    for j_id in self.schd.job_pool.task_jobs.get(tp_id, [])
                ]
            self.schd.job_pool.reload_deltas()
        # Set jobs ref
        self.data[self.workflow_id][JOBS] = self.schd.job_pool.pool
        # Update workflow statuses and totals (assume needed)
        self.update_workflow()

        # Apply current deltas
        self.apply_deltas(reloaded)
        self.updates_pending = False
        self.schd.job_pool.updates_pending = False

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
        for key, info in config.suite_polling_tasks.items():
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
        workflow.name = self.schd.suite
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
        workflow.workflow_log_dir = self.schd.suite_log_dir
        workflow.job_log_names.extend(list(JOB_LOG_OPTS.values()))
        workflow.ns_def_order.extend(config.ns_defn_order)

        workflow.broadcasts = json.dumps(self.schd.broadcast_mgr.broadcasts)

        workflow.tasks.extend(list(tasks))
        workflow.families.extend(list(families))

        self.ancestors = ancestors
        self.descendants = descendants
        self.parents = parents

    def increment_graph_window(
            self, name, point, flow_label,
            edge_distance=0, active_id=None,
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
        s_node = TaskID.get(name, point)
        s_id = f'{self.workflow_id}{ID_DELIM}{point}{ID_DELIM}{name}'
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
                self.prune_pending = True

        # This part is vital to constructing a set of boundary nodes
        # associated with the current Active node.
        if edge_distance > self.n_edge_distance:
            if descendant and self.n_edge_distance > 0:
                self.n_window_boundary_nodes[
                    active_id].setdefault(edge_distance, set()).add(s_id)
            return
        graph_children = generate_graph_children(
            self.schd.config.get_taskdef(name), point)
        if (
                (not any(graph_children.values()) and descendant)
                or self.n_edge_distance == 0
        ):
            self.n_window_boundary_nodes[
                active_id].setdefault(edge_distance, set()).add(s_id)

        self.n_window_nodes[active_id].add(s_id)
        # Generate task node
        self.generate_ghost_task(s_id, name, point, flow_label, is_parent)

        edge_distance += 1

        # TODO: xtrigger is suite_state edges too
        # Reference set for workflow relations
        for items in graph_children.values():
            if edge_distance == 1:
                descendant = True
            self._expand_graph_window(
                s_id, s_node, items, active_id, flow_label, edge_distance,
                descendant, False)

        for items in generate_graph_parents(
                self.schd.config.get_taskdef(name), point).values():
            self._expand_graph_window(
                s_id, s_node, items, active_id, flow_label, edge_distance,
                False, True)

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
            self, s_id, s_node, items, active_id, flow_label, edge_distance,
            descendant=False, is_parent=False):
        """Construct nodes/edges for children/parents of source node."""
        for t_name, t_point, is_abs in items:
            t_node = TaskID.get(t_name, t_point)
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
                t_name, t_point, flow_label,
                copy(edge_distance), active_id, descendant, is_parent)

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
            self.prune_pending = True

    def add_pool_node(self, name, point):
        """Add external ID reference for internal task pool node."""
        tp_id = f'{self.workflow_id}{ID_DELIM}{point}{ID_DELIM}{name}'
        self.all_task_pool.add(tp_id)

    def generate_ghost_task(
            self, tp_id, name, point, flow_label, is_parent=False):
        """Create task-point element populated with static data.

        Args:
            tp_id (str):
                data-store task proxy ID.
            name (str):
                Task name.
            point (cylc.flow.cycling.PointBase):
                PointBase derived object.
            flow_label (str):
                Flow label used to distinguish multiple runs.

        Returns:

            None

        """
        t_id = f'{self.workflow_id}{ID_DELIM}{name}'
        point_string = f'{point}'
        task_proxies = self.data[self.workflow_id][TASK_PROXIES]
        if tp_id in task_proxies or tp_id in self.added[TASK_PROXIES]:
            return

        taskdef = self.data[self.workflow_id][TASKS].get(
            t_id, self.added[TASKS].get(t_id))

        update_time = time()
        tp_stamp = f'{tp_id}@{update_time}'
        tproxy = PbTaskProxy(
            stamp=tp_stamp,
            id=tp_id,
            task=t_id,
            cycle_point=point_string,
            depth=taskdef.depth,
            name=taskdef.name,
            state=TASK_STATUS_WAITING,
            flow_label=flow_label
        )
        if is_parent and tp_id not in self.n_window_nodes:
            # TODO: Load task info from DB
            tproxy.state = TASK_STATUS_EXPIRED
        else:
            tproxy.state = TASK_STATUS_WAITING

        tproxy.namespace[:] = taskdef.namespace
        tproxy.ancestors[:] = [
            f'{self.workflow_id}{ID_DELIM}{point_string}{ID_DELIM}{a_name}'
            for a_name in self.ancestors[taskdef.name]
            if a_name != taskdef.name]
        tproxy.first_parent = tproxy.ancestors[0]

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

    def update_data_structure(self, updated_nodes=None):
        """Workflow batch updates in the data structure."""
        # update states and other dynamic fields
        # TODO: Event driven task proxy updates (non-Batch)
        self.update_dynamic_elements(updated_nodes)
        self.update_family_proxies()

        # Avoids changing window edge distance during edge/node creation
        if self.next_n_edge_distance is not None:
            self.n_edge_distance = self.next_n_edge_distance
            self.next_n_edge_distance = None

        # Update workflow statuses and totals if needed
        if self.prune_pending:
            self.prune_data_store()
        if self.updates_pending:
            self.update_workflow()

        if self.updates_pending or self.schd.job_pool.updates_pending:
            # Apply current deltas
            self.apply_deltas()
            self.updates_pending = False
            self.schd.job_pool.updates_pending = False
            # Gather this batch of deltas for publish
            self.publish_deltas = self.get_publish_deltas()
            # Clear deltas
            self.clear_deltas()

        if self.state_update_families:
            self.updates_pending = True

    def prune_data_store(self):
        """Remove flagged nodes and edges not in the set of active paths."""

        self.prune_pending = False

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
            self.deltas[TASK_PROXIES].pruned.append(tp_id)
            self.schd.job_pool.remove_task_jobs(tp_id)
            self.deltas[EDGES].pruned.extend(node.edges)
            parent_ids.add(node.first_parent)

        prune_ids = set()
        checked_ids = set()
        while parent_ids:
            self._family_ascent_point_prune(
                next(iter(parent_ids)),
                node_ids, parent_ids, checked_ids, prune_ids)
        if prune_ids:
            self.deltas[FAMILY_PROXIES].pruned.extend(prune_ids)
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

    def update_dynamic_elements(self, updated_nodes=None):
        """Update data elements containing dynamic/live fields."""
        # If no tasks are given update all
        if updated_nodes is None:
            updated_nodes = self.schd.pool.get_all_tasks()
        if not updated_nodes:
            return
        self.update_task_proxies(updated_nodes)
        self.updates_pending = True

    def update_task_proxies(self, updated_tasks=None):
        """Update dynamic fields of task nodes/proxies.

        Args:
            updated_tasks (list): [cylc.flow.task_proxy.TaskProxy]
                Update task-node from corresponding given list of
                task proxy objects from the workflow task pool.

        """
        if not updated_tasks:
            return
        tasks = self.data[self.workflow_id][TASKS]
        task_proxies = self.data[self.workflow_id][TASK_PROXIES]
        update_time = time()
        task_defs = {}

        # update task instance
        for itask in updated_tasks:
            name, point_string = TaskID.split(itask.identity)
            tp_id = (
                f'{self.workflow_id}{ID_DELIM}{point_string}{ID_DELIM}{name}')
            if (tp_id not in task_proxies and
                    tp_id not in self.added[TASK_PROXIES]):
                continue
            # Gather task definitions for elapsed time recalculation.
            if name not in task_defs:
                task_defs[name] = itask.tdef
            # Create new message and copy existing message content.
            tp_delta = self.updated[TASK_PROXIES].setdefault(
                tp_id, PbTaskProxy(id=tp_id))
            tp_delta.stamp = f'{tp_id}@{update_time}'
            tp_delta.state = itask.state.status
            if tp_id in task_proxies:
                self.state_update_families.add(
                    task_proxies[tp_id].first_parent)
            else:
                self.state_update_families.add(
                    self.added[TASK_PROXIES][tp_id].first_parent)
            tp_delta.is_held = itask.state.is_held
            tp_delta.flow_label = itask.flow_label
            tp_delta.job_submits = itask.submit_num
            tp_delta.latest_message = itask.summary['latest_message']
            tp_delta.jobs[:] = [
                j_id
                for j_id in self.schd.job_pool.task_jobs.get(tp_id, [])
                if j_id not in task_proxies.get(tp_id, PbTaskProxy()).jobs
            ]
            prereq_list = []
            for prereq in itask.state.prerequisites:
                # Protobuf messages populated within
                prereq_obj = prereq.api_dump(self.workflow_id)
                if prereq_obj:
                    prereq_list.append(prereq_obj)
            tp_delta.prerequisites.extend(prereq_list)
            tp_delta.outputs = json.dumps({
                message: received
                for _, message, received in itask.state.outputs.get_all()
            })
            extras = {}
            if itask.tdef.clocktrigger_offset is not None:
                extras['Clock trigger time reached'] = (
                    itask.is_waiting_clock_done())
                extras['Triggers at'] = time2str(itask.clock_trigger_time)
            for trig, satisfied in itask.state.external_triggers.items():
                key = f'External trigger "{trig}"'
                if satisfied:
                    extras[key] = 'satisfied'
                else:
                    extras[key] = 'NOT satisfied'
            for label, satisfied in itask.state.xtriggers.items():
                sig = self.schd.xtrigger_mgr.get_xtrig_ctx(
                    itask, label).get_signature()
                extra = f'xtrigger "{label} = {sig}"'
                if satisfied:
                    extras[extra] = 'satisfied'
                else:
                    extras[extra] = 'NOT satisfied'
            tp_delta.extras = json.dumps(extras)

        # Recalculate effected task def elements elapsed time.
        for name, tdef in task_defs.items():
            elapsed_time = task_mean_elapsed_time(tdef)
            if elapsed_time:
                t_id = f'{self.workflow_id}{ID_DELIM}{name}'
                t_delta = PbTask(
                    stamp=f'{t_id}@{update_time}',
                    mean_elapsed_time=elapsed_time
                )
                self.updated[TASKS].setdefault(
                    t_id,
                    PbTask(id=t_id)).MergeFrom(t_delta)
                tasks[t_id].MergeFrom(t_delta)

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
            # gather child states for count and set is_held
            state_counter = Counter({})
            is_held_total = 0
            for child_id in fam_node.child_families:
                child_node = fp_updated.get(child_id, fp_data.get(child_id))
                if child_node is not None:
                    is_held_total += child_node.is_held_total
                    state_counter += Counter(dict(child_node.state_totals))
            task_states = []
            for tp_id in fam_node.child_tasks:
                tp_node = tp_updated.get(tp_id)
                if tp_node is None or not tp_node.state:
                    tp_node = tp_added.get(tp_id, tp_data.get(tp_id))
                if tp_node is not None:
                    if tp_node.state:
                        task_states.append(tp_node.state)
                    if tp_node.is_held:
                        is_held_total += 1
            state_counter += Counter(task_states)
            # created delta data element
            fp_delta = PbFamilyProxy(
                id=fp_id,
                stamp=f'{fp_id}@{time()}',
                state=extract_group_state(state_counter.keys()),
                is_held=(is_held_total > 0),
                is_held_total=is_held_total
            )
            fp_delta.states[:] = state_counter.keys()
            for state, state_cnt in state_counter.items():
                fp_delta.state_totals[state] = state_cnt
            fp_updated.setdefault(fp_id, PbFamilyProxy()).MergeFrom(fp_delta)
            # mark as updated in case parent family is updated next
            self.updated_state_families.add(fp_id)
            # mark parent for update
            if fam_node.first_parent:
                self.state_update_families.add(fam_node.first_parent)
            self.state_update_families.remove(fp_id)

    def hold_release_tasks(self, hold=True):
        """Hold or release all task nodes in the graph window."""
        # Needed, as not all data-store tasks are in the task pool
        tp_data = self.data[self.workflow_id][TASK_PROXIES]
        tp_added = self.added[TASK_PROXIES]
        update_time = time()
        for tp_node in list(tp_data.values()) + list(tp_added.values()):
            if tp_node.is_held is hold:
                continue
            tp_delta = self.updated[TASK_PROXIES].setdefault(
                tp_node.id, PbTaskProxy(id=tp_node.id))
            tp_delta.stamp = f'{tp_node.id}@{update_time}'
            tp_delta.is_held = hold
            tp_delta.state = tp_node.state
            self.state_update_families.add(tp_node.first_parent)

    def set_graph_window_extent(self, n_edge_distance):
        """Set what the max edge distance will change to.

        Args:
            n_edge_distance (int):
                Maximum edge distance from active node.

        """
        self.next_n_edge_distance = n_edge_distance
        self.updates_pending = True

    def set_workflow_ports(self):
        # Create new message and copy existing message content
        workflow = self.updated[WORKFLOW]
        workflow.id = self.workflow_id
        workflow.last_updated = time()
        workflow.stamp = f'{workflow.id}@{workflow.last_updated}'

        workflow.port = self.schd.port
        workflow.pub_port = self.schd.pub_port

        self.updates_pending = True

    def update_workflow(self):
        """Update workflow element status and state totals."""
        # Create new message and copy existing message content
        workflow = self.updated[WORKFLOW]
        workflow.id = self.workflow_id
        workflow.last_updated = time()
        workflow.stamp = f'{workflow.id}@{workflow.last_updated}'

        data = self.data[self.workflow_id]

        # new updates/deltas not applied yet
        # so need to search/use updated states if available.
        state_counter = Counter({})
        is_held_total = 0
        for root_id in set(
                [n.id
                 for n in data[FAMILY_PROXIES].values()
                 if n.name == 'root'] +
                [n.id
                 for n in self.added[FAMILY_PROXIES].values()
                 if n.name == 'root']
        ):
            root_node = self.updated[FAMILY_PROXIES].get(
                root_id, data.get(root_id))
            if root_node is not None and root_node.state:
                is_held_total += root_node.is_held_total
                state_counter += Counter(dict(root_node.state_totals))
        workflow.states[:] = state_counter.keys()
        for state, state_cnt in state_counter.items():
            workflow.state_totals[state] = state_cnt

        workflow.is_held_total = is_held_total

        # Construct a workflow status string for use by monitoring clients.
        workflow.status, workflow.status_msg = map(
            str, get_suite_status(self.schd))

        if self.schd.pool.pool:
            pool_points = set(self.schd.pool.pool)
            workflow.oldest_cycle_point = str(min(pool_points))
            workflow.newest_cycle_point = str(max(pool_points))
        if self.schd.pool.runahead_pool:
            workflow.newest_runahead_cycle_point = str(
                max(set(self.schd.pool.runahead_pool))
            )

    # TODO: Make the other deltas/updates event driven like this one.
    def delta_broadcast(self):
        """Collects broadcasts on change event."""
        workflow = self.updated[WORKFLOW]
        workflow.broadcasts = json.dumps(self.schd.broadcast_mgr.broadcasts)
        self.updates_pending = True

    def apply_deltas(self, reloaded=False):
        """Gather and apply deltas."""
        # Copy in job deltas
        self.deltas[JOBS].CopyFrom(self.schd.job_pool.deltas)
        self.added[JOBS] = deepcopy(self.schd.job_pool.added)
        self.updated[JOBS] = deepcopy(self.schd.job_pool.updated)
        if self.added[JOBS]:
            getattr(self.updated[WORKFLOW], JOBS).extend(
                self.added[JOBS].keys())

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

        # Clear job pool changes after their application
        self.schd.job_pool.deltas.Clear()
        self.schd.job_pool.added.clear()
        self.schd.job_pool.updated.clear()

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

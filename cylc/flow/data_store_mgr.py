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

Updates are triggered by changes in the task pool;
migrations of task instances from runahead to live pool, and
changes in task state (itask.state.is_updated).
- Graph edges are generated for new cycle points in the pool
- Ghost nodes, task and family cycle point instances containing static data,
  are generated from the source & target of edges and pointwise respectively.
- Cycle points are removed/pruned if they are not in the pool and not
  the source or target cycle point of the current edge set. The removed include
  edge, task, and family cycle point items and an update of the family,
  workflow, and manager aggregate attributes.

Data elements include a "stamp" field, which is a timestamped ID for use
in assessing changes in the data store, for comparisons of a store sync.

Packaging methods are included for dissemination of protobuf messages.

"""

from collections import Counter
from copy import deepcopy
from time import time
import zlib

from cylc.flow import __version__ as CYLC_VERSION, ID_DELIM
from cylc.flow.cycling.loader import get_point
from cylc.flow.data_messages_pb2 import (
    PbEdge, PbEntireWorkflow, PbFamily, PbFamilyProxy,
    PbJob, PbTask, PbTaskProxy, PbWorkflow,
    EDeltas, FDeltas, FPDeltas, JDeltas, TDeltas, TPDeltas)
from cylc.flow.network import API
from cylc.flow.suite_status import get_suite_status
from cylc.flow.task_id import TaskID
from cylc.flow.task_job_logs import JOB_LOG_OPTS
from cylc.flow.task_state_prop import extract_group_state
from cylc.flow.wallclock import (
    TIME_ZONE_LOCAL_INFO, TIME_ZONE_UTC_INFO, get_utc_mode)


EDGES = 'edges'
FAMILIES = 'families'
FAMILY_PROXIES = 'family_proxies'
JOBS = 'jobs'
TASKS = 'tasks'
TASK_PROXIES = 'task_proxies'
WORKFLOW = 'workflow'

MESSAGE_MAP = {
    EDGES: PbEdge,
    FAMILIES: PbFamily,
    FAMILY_PROXIES: PbFamilyProxy,
    JOBS: PbJob,
    TASKS: PbTask,
    TASK_PROXIES: PbTaskProxy,
    WORKFLOW: PbWorkflow,
}

DELTAS_MAP = {
    EDGES: EDeltas,
    FAMILIES: FDeltas,
    FAMILY_PROXIES: FPDeltas,
    JOBS: JDeltas,
    TASKS: TDeltas,
    TASK_PROXIES: TPDeltas,
    WORKFLOW: PbWorkflow,
}

# Protobuf message merging appends repeated field results on merge,
# unlike singular fields which are overwritten. This behaviour is
# desirable in many cases, but there are exceptions.
# The following is used to flag which fields require clearing before
# merging from respective deltas messages.
CLEAR_FIELD_MAP = {
    EDGES: set(),
    FAMILIES: set(),
    FAMILY_PROXIES: set(),
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
    return tdef.rtconfig['job'].get('execution time limit', None)


def apply_delta(key, delta, data):
    """Apply delta to specific data-store workflow and type."""
    # Merge in updated fields
    if key == WORKFLOW:
        # Clear fields the require overwrite with delta
        for field in CLEAR_FIELD_MAP[key]:
            data[key].ClearField(field)
        data[key].MergeFrom(delta)
        return
    for element in delta.deltas:
        if element.id not in data[key]:
            data[key][element.id] = MESSAGE_MAP[key]()
        else:
            # Clear fields the require overwrite with delta
            for field, _ in element.ListFields():
                if field.name in CLEAR_FIELD_MAP[key]:
                    data[key][element.id].ClearField(field.name)
        data[key][element.id].MergeFrom(element)
    # Prune data elements by id
    for del_id in delta.pruned:
        if del_id not in data[key]:
            continue
        if key == TASK_PROXIES:
            data[TASKS][data[key][del_id].task].proxies.remove(del_id)
            getattr(data[WORKFLOW], key).remove(del_id)
        elif key == FAMILY_PROXIES:
            data[FAMILIES][data[key][del_id].family].proxies.remove(del_id)
            getattr(data[WORKFLOW], key).remove(del_id)
        elif key == EDGES:
            getattr(data[WORKFLOW], key).edges.remove(del_id)
        del data[key][del_id]


class DataStoreMgr:
    """Manage the workflow data store.

    Attributes:
        .ancestors (dict):
            Local store of config.get_first_parent_ancestors()
        .cycle_states (dict):
            Contains dict of task and tuple (state, is_held) pairs
            for each cycle point key.
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
        .edge_points (dict):
            Source point keys of target points lists.
        .max_point (cylc.flow.cycling.PointBase):
            Maximum cycle point in the pool.
        .min_point (cylc.flow.cycling.PointBase):
            Minimum cycle point in the pool.
        .parents (dict):
            Local store of config.get_parent_lists()
        .pool_points (set):
            Cycle point objects in the task pool.
        .schd (cylc.flow.scheduler.Scheduler):
            Workflow scheduler object.
        .workflow_id (str):
            ID of the workflow service containing owner and name.

    Arguments:
        schd (cylc.flow.scheduler.Scheduler):
            Workflow scheduler instance.
    """

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = [
        'ancestors',
        'cycle_states',
        'data',
        'deltas',
        'descendants',
        'edge_points',
        'max_point',
        'min_point',
        'parents',
        'pool_points',
        'schd',
        'updates',
        'updates_pending',
        'workflow_id',
    ]

    def __init__(self, schd):
        self.schd = schd
        self.workflow_id = f'{self.schd.owner}{ID_DELIM}{self.schd.suite}'
        self.ancestors = {}
        self.descendants = {}
        self.parents = {}
        self.pool_points = set()
        self.max_point = None
        self.min_point = None
        self.edge_points = {}
        self.cycle_states = {}
        # Managed data types
        self.data = {
            self.workflow_id: {
                EDGES: {},
                FAMILIES: {},
                FAMILY_PROXIES: {},
                JOBS: {},
                TASKS: {},
                TASK_PROXIES: {},
                WORKFLOW: PbWorkflow(),
            }
        }
        self.deltas = {
            EDGES: EDeltas(),
            FAMILIES: FDeltas(),
            FAMILY_PROXIES: FPDeltas(),
            JOBS: JDeltas(),
            TASKS: TDeltas(),
            TASK_PROXIES: TPDeltas(),
            WORKFLOW: PbWorkflow(),
        }
        self.updates = {
            EDGES: {},
            FAMILIES: {},
            FAMILY_PROXIES: {},
            JOBS: {},
            TASKS: {},
            TASK_PROXIES: {},
        }
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
        self.increment_graph_elements()

        # Tidy and reassign task jobs after reload
        if reloaded:
            new_tasks = set(self.updates[TASK_PROXIES])
            job_tasks = set(self.schd.job_pool.task_jobs)
            for tp_id in job_tasks.difference(new_tasks):
                self.schd.job_pool.remove_task_jobs(tp_id)
            for tp_id, tp_delta in self.updates[TASK_PROXIES].items():
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

    def generate_definition_elements(self):
        """Generate static definition data elements.

        Populates the tasks, families, and workflow elements
        with data from and/or derived from the workflow definition.

        """
        config = self.schd.config
        update_time = time()
        tasks = self.updates[TASKS]
        families = self.updates[FAMILIES]
        workflow = self.deltas[WORKFLOW]
        workflow.id = self.workflow_id
        workflow.last_updated = update_time

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

        # Create task definition elements.
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
            for key, val in dict(tdef.describe()).items():
                if key in ['title', 'description', 'URL']:
                    setattr(task.meta, key, val)
                else:
                    task.meta.user_defined.append(f'{key}={val}')
            elapsed_time = task_mean_elapsed_time(tdef)
            if elapsed_time:
                task.mean_elapsed_time = elapsed_time
            tasks[t_id] = task

        # Created family definition elements.
        for name in ancestors.keys():
            if name in config.taskdefs.keys():
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
            for key, val in famcfg.get('meta', {}).items():
                if key in ['title', 'description', 'URL']:
                    setattr(family.meta, key, val)
                else:
                    family.meta.user_defined.append(f'{key}={val}')
            family.parents.extend(
                [f'{self.workflow_id}{ID_DELIM}{p_name}'
                 for p_name in parents[name]])
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
        workflow.port = self.schd.port
        for key, val in config.cfg['meta'].items():
            if key in ['title', 'description', 'URL']:
                setattr(workflow.meta, key, val)
            else:
                workflow.meta.user_defined.append(f'{key}={val}')
        workflow.tree_depth = max(
            [len(val) for key, val in ancestors.items()]) - 1

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
        workflow.ns_defn_order.extend(config.ns_defn_order)

        workflow.tasks.extend(list(tasks))
        workflow.families.extend(list(families))

        self.ancestors = ancestors
        self.descendants = descendants
        self.parents = parents

    def generate_ghost_task(self, task_id):
        """Create task-point element populated with static data.

        Args:
            task_id (str):
                valid TaskID string.

        Returns:

            object: cylc.flow.data_messages_pb2.PbTaskProxy
                Populated task proxy data element.

        """
        update_time = time()

        name, point_string = TaskID.split(task_id)
        self.cycle_states.setdefault(point_string, {})[name] = (None, False)
        t_id = f'{self.workflow_id}{ID_DELIM}{name}'
        tp_id = f'{self.workflow_id}{ID_DELIM}{point_string}{ID_DELIM}{name}'
        tp_stamp = f'{tp_id}@{update_time}'
        taskdef = self.data[self.workflow_id][TASKS].get(
            t_id,
            self.updates[TASKS].get(t_id, MESSAGE_MAP[TASKS])
        )
        tproxy = PbTaskProxy(
            stamp=tp_stamp,
            id=tp_id,
            task=taskdef.id,
            cycle_point=point_string,
            depth=taskdef.depth,
            name=name,
        )
        tproxy.namespace[:] = taskdef.namespace
        tproxy.parents[:] = [
            f'{self.workflow_id}{ID_DELIM}{point_string}{ID_DELIM}{p_name}'
            for p_name in self.parents[name]]
        tproxy.ancestors[:] = [
            f'{self.workflow_id}{ID_DELIM}{point_string}{ID_DELIM}{a_name}'
            for a_name in self.ancestors[name]
            if a_name != name]
        tproxy.first_parent = tproxy.ancestors[0]
        return tproxy

    def generate_ghost_families(self, cycle_points=None):
        """Generate the family-point elements from tasks in cycle points.

        Args:
            cycle_points (set):
                a set of cycle points.

        Returns:
            list: [cylc.flow.data_messages_pb2.PbFamilyProxy]
                list of populated family proxy data elements.

        """
        update_time = time()
        families = self.data[self.workflow_id][FAMILIES]
        if not families:
            families = self.updates[FAMILIES]
        family_proxies = self.data[self.workflow_id][FAMILY_PROXIES]
        for point_string, tasks in self.cycle_states.items():
            # construct family tree based on the
            # first-parent single-inheritance tree
            if not cycle_points or point_string not in cycle_points:
                continue
            cycle_first_parents = set()

            for key in tasks:
                for parent in self.ancestors.get(key, []):
                    if parent == key:
                        continue
                    cycle_first_parents.add(parent)

            for f_id in families:
                fam = families[f_id].name
                fp_id = (
                    f'{self.workflow_id}{ID_DELIM}'
                    f'{point_string}{ID_DELIM}{fam}')
                if (fp_id in family_proxies or
                        fp_id in self.updates[FAMILY_PROXIES]):
                    continue
                fp_delta = PbFamilyProxy(
                    stamp=f'{fp_id}@{update_time}',
                    id=fp_id,
                    cycle_point=point_string,
                    name=fam,
                    family=f'{self.workflow_id}{ID_DELIM}{fam}',
                    depth=families[f_id].depth,
                )
                fp_delta.parents[:] = [
                    f'{self.workflow_id}{ID_DELIM}'
                    f'{point_string}{ID_DELIM}{p_name}'
                    for p_name in self.parents[fam]]
                fp_delta.ancestors[:] = [
                    f'{self.workflow_id}{ID_DELIM}'
                    f'{point_string}{ID_DELIM}{a_name}'
                    for a_name in self.ancestors[fam]
                    if a_name != fam]
                if fp_delta.ancestors:
                    fp_delta.first_parent = fp_delta.ancestors[0]
                if fam in cycle_first_parents:
                    for child_name in self.descendants[fam]:
                        ch_id = (
                            f'{self.workflow_id}{ID_DELIM}'
                            f'{point_string}{ID_DELIM}{child_name}'
                        )
                        if self.parents[child_name][0] == fam:
                            if child_name in cycle_first_parents:
                                fp_delta.child_families.append(ch_id)
                            elif child_name in self.schd.config.taskdefs:
                                fp_delta.child_tasks.append(ch_id)
                self.updates[FAMILY_PROXIES][fp_id] = fp_delta

                # Add ref ID to family element
                f_delta = PbFamily(
                    id=f_id,
                    stamp=f'{f_id}@{update_time}')
                f_delta.proxies.append(fp_id)
                self.updates[FAMILIES].setdefault(
                    f_id, PbFamily(id=f_id)).MergeFrom(f_delta)

                # Add ref ID to workflow element
                getattr(self.deltas[WORKFLOW], FAMILY_PROXIES).append(fp_id)

    def generate_graph_elements(self, start_point=None, stop_point=None):
        """Generate edges and [ghost] nodes (family and task proxy elements).

        Args:
            start_point (cylc.flow.cycling.PointBase):
                Edge generation start point.
            stop_point (cylc.flow.cycling.PointBase):
                Edge generation stop point.

        """
        if not self.pool_points:
            return
        config = self.schd.config
        tasks = self.data[self.workflow_id][TASKS]
        if not tasks:
            tasks = self.updates[TASKS]
        task_proxies = self.data[self.workflow_id][TASK_PROXIES]
        if start_point is None:
            start_point = min(self.pool_points)
        if stop_point is None:
            stop_point = max(self.pool_points)

        # Used for generating family [ghost] nodes
        new_points = set()

        # Generate ungrouped edges
        for edge in config.get_graph_edges(start_point, stop_point):
            # Reference or create edge source & target nodes/proxies
            s_node = edge[0]
            t_node = edge[1]
            if s_node is None:
                continue
            # Is the source cycle point in the task pool?
            s_name, s_point = TaskID.split(s_node)
            s_point_cls = get_point(s_point)
            s_pool_point = False
            s_valid = TaskID.is_valid_id(s_node)
            if s_valid:
                s_pool_point = s_point_cls in self.pool_points
            # Is the target cycle point in the task pool?
            t_pool_point = False
            t_valid = t_node and TaskID.is_valid_id(t_node)
            if t_valid:
                t_name, t_point = TaskID.split(t_node)
                t_point_cls = get_point(t_point)
                t_pool_point = get_point(t_point) in self.pool_points
            # Proceed if either source or target cycle points
            # are in the task pool.
            if not s_pool_point and not t_pool_point:
                continue
            # If source/target is valid add/create the corresponding items.
            # TODO: if xtrigger is suite_state create remote ID
            source_id = (
                f'{self.workflow_id}{ID_DELIM}{s_point}{ID_DELIM}{s_name}')
            if s_valid:
                s_task_id = f'{self.workflow_id}{ID_DELIM}{s_name}'
                new_points.add(s_point)
                # Add source points for pruning.
                self.edge_points.setdefault(s_point_cls, set())
                if (source_id not in task_proxies and
                        source_id not in self.updates[TASK_PROXIES]):
                    self.updates[TASK_PROXIES][source_id] = (
                        self.generate_ghost_task(s_node))
                    getattr(
                        self.deltas[WORKFLOW], TASK_PROXIES).append(source_id)
                if (source_id not in tasks[s_task_id].proxies and
                        source_id not in self.updates[TASKS].get(
                            s_task_id, PbTask()).proxies):
                    self.updates[TASKS].setdefault(
                        s_task_id,
                        PbTask(
                            stamp='f{s_task_id}@{update_time}',
                            id=s_task_id,
                        )).proxies.append(source_id)
            # Add valid source before checking for no target,
            # as source may be an isolate (hence no edges).
            # At present targets can't be xtriggers.
            if t_valid:
                target_id = (
                    f'{self.workflow_id}{ID_DELIM}{t_point}{ID_DELIM}{t_name}')
                t_task_id = f'{self.workflow_id}{ID_DELIM}{t_name}'
                new_points.add(t_point)
                # Add target points to associated source points for pruning.
                self.edge_points.setdefault(s_point_cls, set())
                self.edge_points[s_point_cls].add(t_point_cls)
                if (target_id not in task_proxies and
                        target_id not in self.updates[TASK_PROXIES]):
                    self.updates[TASK_PROXIES][target_id] = (
                        self.generate_ghost_task(t_node))
                    getattr(self.deltas[WORKFLOW], TASK_PROXIES).append(
                        target_id)
                if (target_id not in tasks[t_task_id].proxies and
                        target_id not in self.updates[TASKS].get(
                            t_task_id, PbTask()).proxies):
                    self.updates[TASKS].setdefault(
                        t_task_id,
                        PbTask(
                            stamp='f{t_task_id}@{update_time}',
                            id=t_task_id,
                        )).proxies.append(target_id)

                # Initiate edge element.
                e_id = (
                    f'{self.workflow_id}{ID_DELIM}{s_node}{ID_DELIM}{t_node}')
                self.updates[EDGES][e_id] = PbEdge(
                    id=e_id,
                    suicide=edge[3],
                    cond=edge[4],
                    source=source_id,
                    target=target_id,
                )

                # Add edge id to node field for resolver reference
                self.updates[TASK_PROXIES].setdefault(
                    target_id,
                    PbTaskProxy(id=target_id)).edges.append(e_id)
                if s_valid:
                    self.updates[TASK_PROXIES].setdefault(
                        source_id,
                        PbTaskProxy(id=source_id)).edges.append(e_id)

        getattr(
            self.deltas.setdefault(WORKFLOW, PbWorkflow()),
            EDGES).edges.extend(self.updates[EDGES].keys())
        if new_points:
            self.generate_ghost_families(new_points)

    def update_data_structure(self, updated_nodes=None):
        """Reflect workflow changes in the data structure."""
        # Clear previous deltas
        self.clear_deltas()

        # Update edges & node set
        self.increment_graph_elements()
        # update states and other dynamic fields
        self.update_dynamic_elements(updated_nodes)

        # Update workflow statuses and totals if needed
        if self.updates_pending:
            self.update_workflow()

        if self.updates_pending or self.schd.job_pool.updates_pending:
            # Apply current deltas
            self.apply_deltas()
            self.updates_pending = False
            self.schd.job_pool.updates_pending = False

    def increment_graph_elements(self):
        """Generate and/or prune graph elements if needed.

        Use the task pool and edge source/target cycle points to find
        new points to generate edges and/or old points to prune data-store.

        """
        # Gather task pool cycle points.
        old_pool_points = self.pool_points.copy()
        self.pool_points = set(self.schd.pool.pool)
        # No action if pool is not yet initiated.
        if not self.pool_points:
            return
        # Increment edges:
        # - Initially for each cycle point in the pool.
        # - For each new cycle point thereafter.
        # Using difference and pointwise allows for historical
        # task insertion (in gaps).
        new_points = self.pool_points.difference(old_pool_points)
        if new_points:
            for point in new_points:
                # All family & task cycle instances are generated and
                # populated with static data as 'ghost nodes'.
                self.generate_graph_elements(point, point)
            self.min_point = min(self.pool_points)
            self.max_point = max(self.pool_points)
        # Prune data store by cycle point where said point is:
        # - Not in the set of pool points.
        # - Not a source or target cycle point in the set of edges.
        # This ensures a buffer of sources and targets in front and behind the
        # task pool, while accommodating exceptions such as ICP dependencies.
        # TODO: Turn nodes back to ghost if not in pool? (for suicide)
        prune_points = set()
        for s_point, t_points in list(self.edge_points.items()):
            if (s_point not in self.pool_points and
                    t_points.isdisjoint(self.pool_points)):
                prune_points.add(str(s_point))
                prune_points.update((str(t_p) for t_p in t_points))
                del self.edge_points[s_point]
                continue
            t_diffs = t_points.difference(self.pool_points)
            if t_diffs:
                prune_points.update((str(t_p) for t_p in t_diffs))
                self.edge_points[s_point].difference_update(t_diffs)
        # Action pruning if any eligible cycle points are found.
        if prune_points:
            self.prune_points(prune_points)
        if new_points or prune_points:
            # Pruned and/or additional elements require
            # state/status recalculation, and ID ref updates.
            self.updates_pending = True

    def prune_points(self, point_strings):
        """Remove old nodes and edges by cycle point.

        Args:
            point_strings (iterable):
                Iterable of valid cycle point strings.

        """
        flow_data = self.data[self.workflow_id]
        if not point_strings:
            return
        node_ids = set()
        for tp_id, tproxy in list(flow_data[TASK_PROXIES].items()):
            if tproxy.cycle_point in point_strings:
                node_ids.add(tp_id)
                self.deltas[TASK_PROXIES].pruned.append(tp_id)
                self.schd.job_pool.remove_task_jobs(tp_id)

        for fp_id, fproxy in list(flow_data[FAMILY_PROXIES].items()):
            if fproxy.cycle_point in point_strings:
                self.deltas[FAMILY_PROXIES].pruned.append(fp_id)

        for e_id, edge in list(flow_data[EDGES].items()):
            if edge.source in node_ids or edge.target in node_ids:
                self.deltas[EDGES].pruned.append(e_id)

        for point_string in point_strings:
            try:
                del self.cycle_states[point_string]
            except KeyError:
                continue

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
                    tp_id not in self.updates[TASK_PROXIES]):
                continue
            self.cycle_states.setdefault(point_string, {})[name] = (
                itask.state.status, itask.state.is_held)
            # Gather task definitions for elapsed time recalculation.
            if name not in task_defs:
                task_defs[name] = itask.tdef
            # Create new message and copy existing message content.
            tp_delta = self.updates[TASK_PROXIES].setdefault(
                tp_id, PbTaskProxy(id=tp_id))
            tp_delta.stamp = f'{tp_id}@{update_time}'
            tp_delta.state = itask.state.status
            tp_delta.is_held = itask.state.is_held
            tp_delta.job_submits = itask.submit_num
            tp_delta.spawned = itask.has_spawned
            tp_delta.latest_message = itask.summary['latest_message']
            tp_delta.jobs[:] = [
                j_id
                for j_id in self.schd.job_pool.task_jobs.get(tp_id, [])
                if j_id not in task_proxies.get(tp_id, PbTaskProxy()).jobs
            ]
            tp_delta.broadcasts[:] = [
                f'{key}={val}' for key, val in
                self.schd.task_events_mgr.broadcast_mgr.get_broadcast(
                    itask.identity).items()]
            prereq_list = []
            for prereq in itask.state.prerequisites:
                # Protobuf messages populated within
                prereq_obj = prereq.api_dump(self.workflow_id)
                if prereq_obj:
                    prereq_list.append(prereq_obj)
            tp_delta.prerequisites.extend(prereq_list)
            tp_delta.outputs[:] = [
                f'{trigger}={is_completed}'
                for trigger, _, is_completed in itask.state.outputs.get_all()
            ]

        # Recalculate effected task def elements elapsed time.
        for name, tdef in task_defs.items():
            elapsed_time = task_mean_elapsed_time(tdef)
            if elapsed_time:
                t_id = f'{self.workflow_id}{ID_DELIM}{name}'
                t_delta = PbTask(
                    stamp=f'{t_id}@{update_time}',
                    mean_elapsed_time=elapsed_time
                )
                self.updates[TASKS].setdefault(
                    t_id,
                    PbTask(id=t_id)).MergeFrom(t_delta)
                tasks[t_id].MergeFrom(t_delta)

    def update_family_proxies(self, cycle_points=None):
        """Update state of family proxies.

        Args:
            cycle_points (list):
                Update family-node state from given list of
                valid cycle point strings.

        """
        family_proxies = self.data[self.workflow_id][FAMILY_PROXIES]
        if cycle_points is None:
            cycle_points = self.cycle_states.keys()
        if not cycle_points:
            return
        update_time = time()

        for point_string in cycle_points:
            # For each cycle point, construct a family state tree
            # based on the first-parent single-inheritance tree
            c_task_states = self.cycle_states.get(point_string, None)
            if c_task_states is None:
                continue
            c_fam_task_states = {}
            c_fam_task_is_held = {}

            for key in c_task_states:
                state, is_held = c_task_states[key]
                if state is None:
                    continue

                for parent in self.ancestors.get(key, []):
                    if parent == key:
                        continue
                    c_fam_task_states.setdefault(parent, set())
                    c_fam_task_states[parent].add(state)
                    c_fam_task_is_held.setdefault(parent, False)
                    if is_held:
                        c_fam_task_is_held[parent] = is_held

            for fam, child_states in c_fam_task_states.items():
                state = extract_group_state(child_states)
                fp_id = (
                    f'{self.workflow_id}{ID_DELIM}'
                    f'{point_string}{ID_DELIM}{fam}')
                if state is None or (
                        fp_id not in family_proxies and
                        fp_id not in self.updates[FAMILY_PROXIES]):
                    continue
                # Since two fields strings are reassigned,
                # it should be safe without copy.
                fp_delta = PbFamilyProxy(
                    id=fp_id,
                    stamp=f'{fp_id}@{update_time}',
                    state=state,
                    is_held=c_fam_task_is_held[fam]
                )
                self.updates[FAMILY_PROXIES].setdefault(
                    fp_id, PbFamilyProxy()).MergeFrom(fp_delta)

    def update_workflow(self):
        """Update workflow element status and state totals."""
        # Create new message and copy existing message content
        update_time = time()
        workflow = self.deltas[WORKFLOW]
        workflow.last_updated = update_time

        data = self.data[self.workflow_id]

        # new updates/deltas not applied yet
        # so need to search/use updated states if available.
        counter = Counter(
            [t.state
             for t in data[TASK_PROXIES].values()
             if t.state and t.id not in self.updates[TASK_PROXIES]] +
            [t.state
             for t in self.updates[TASK_PROXIES].values()
             if t.state]
        )

        workflow.states[:] = counter.keys()
        for state, state_cnt in counter.items():
            workflow.state_totals[state] = state_cnt

        workflow.is_held_total = len(
            [t.is_held
             for t in data[TASK_PROXIES].values()
             if t.is_held and t.id not in self.updates[TASK_PROXIES]] +
            [t.is_held
             for t in self.updates[TASK_PROXIES].values()
             if t.is_held]
        )

        # Construct a workflow status string for use by monitoring clients.
        workflow.status, workflow.status_msg = map(
            str, get_suite_status(self.schd))

        for key, value in (
                ('oldest_cycle_point', self.min_point),
                ('newest_cycle_point', self.max_point),
                ('newest_runahead_cycle_point',
                 self.schd.pool.get_max_point_runahead())):
            if value:
                setattr(workflow, key, str(value))

    def update_dynamic_elements(self, updated_nodes=None):
        """Update data elements containing dynamic/live fields."""
        # If no tasks are given update all
        if updated_nodes is None:
            updated_nodes = self.schd.pool.get_all_tasks()
        elif not updated_nodes:
            return
        self.update_task_proxies(updated_nodes)
        self.update_family_proxies(set(str(t.point) for t in updated_nodes))
        self.updates_pending = True

    def clear_deltas(self):
        """Clear current deltas."""
        for key in self.deltas:
            if key in self.deltas:
                self.deltas[key].Clear()
            if key in self.updates:
                self.updates[key].clear()

    def apply_deltas(self, reloaded=False):
        """Gather and apply deltas."""
        # Copy in job deltas
        self.deltas[JOBS].CopyFrom(self.schd.job_pool.deltas)
        self.updates[JOBS] = deepcopy(self.schd.job_pool.updates)

        # Gather cumulative update elements
        for key, elements in self.updates.items():
            self.deltas[key].deltas.extend(elements.values())

        # Apply deltas to local data-store
        data = self.data[self.workflow_id]
        for key, delta in self.deltas.items():
            delta.reloaded = reloaded
            apply_delta(key, delta, data)

        # Construct checksum on deltas for export
        update_time = time()
        for key, delta in self.deltas.items():
            if delta.ListFields() and hasattr(delta, 'checksum'):
                delta.time = update_time
                if key == EDGES:
                    s_att = 'id'
                else:
                    s_att = 'stamp'
                delta.checksum = generate_checksum(
                    [getattr(e, s_att) for e in data[key].values()])

        # Clear job pool changes after their application
        self.schd.job_pool.deltas.Clear()
        self.schd.job_pool.updates.clear()

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
        return [
            (key.encode('utf-8'), delta, 'SerializeToString')
            for key, delta in self.deltas.items()
            if delta.ListFields()
        ]

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
        if element_type == WORKFLOW:
            pb_msg.CopyFrom(data[WORKFLOW])
        else:
            pb_msg.time = data[WORKFLOW].last_updated
            pb_msg.deltas.extend(data[element_type].values())
        return pb_msg

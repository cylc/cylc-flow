#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Manage the data feed for the User Interface Server."""

from time import time
from copy import copy, deepcopy
import ast

from cylc.flow.task_id import TaskID
from cylc.flow.suite_status import (
    SUITE_STATUS_HELD, SUITE_STATUS_STOPPING,
    SUITE_STATUS_RUNNING, SUITE_STATUS_RUNNING_TO_STOP,
    SUITE_STATUS_RUNNING_TO_HOLD)
from cylc.flow.task_state_prop import extract_group_state
from cylc.flow.wallclock import (
    TIME_ZONE_LOCAL_INFO, TIME_ZONE_UTC_INFO, get_utc_mode)
from cylc.flow.task_job_logs import JOB_LOG_OPTS
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.ws_messages_pb2 import (
    PbFamily, PbFamilyProxy, PbTask, PbTaskProxy, PbWorkflow,
    PbEdge, PbEdges, PbEntireWorkflow)


class WsDataMgr(object):
    """Manage the data feed for the User Interface Server."""

    TIME_FIELDS = ['submitted_time', 'started_time', 'finished_time']

    def __init__(self, schd):
        self.schd = schd
        self.ancestors = {}
        self.descendants = {}
        self.parents = {}
        self.cycle_states = {}
        self.all_states = []
        self.state_count_cycles = {}
        # managed data
        self.tasks = {}
        self.task_proxies = {}
        self.families = {}
        self.family_proxies = {}
        self.edges = {}
        self.graph = PbEdges()
        self.workflow_id = f"{self.schd.owner}/{self.schd.suite}"
        self.workflow = PbWorkflow()

    # The following method is inefficiently run on any change
    # TODO: Add more update methods:
    # - incremental graph generation and pruning (using cycle points)
    # - incremental state updates using itask.state.is_updated
    def initiate_data_model(self):
        """Initiate or Update data model on start/reload."""
        self.generate_definition_elements()
        self.generate_graph_elements()
        self.update_task_proxies()
        self.update_family_proxies()
        self.update_workflow()

    def generate_definition_elements(self):
        """Generate static definition data elements"""
        config = self.schd.config
        update_time = time()
        tasks = {}
        families = {}
        workflow = PbWorkflow(
            checksum=f"{self.workflow_id}@{update_time}",
            id=self.workflow_id,
        )

        ancestors = config.get_first_parent_ancestors()
        descendants = config.get_first_parent_descendants()
        parents = config.get_parent_lists()

        # create task definition data objects
        for name, tdef in config.taskdefs.items():
            t_id = f"{self.workflow_id}/{name}"
            t_check = f"{name}@{update_time}"
            task = PbTask(
                checksum=t_check,
                id=t_id,
                name=name,
                depth=len(ancestors[name]) - 1,
            )
            task.namespace[:] = tdef.namespace_hierarchy
            for key, val in dict(tdef.describe()).items():
                if key in ['title', 'description', 'url']:
                    setattr(task.meta, key, val)
                else:
                    task.meta.user_defined.append(f"{key}={val}")
            ntimes = len(tdef.elapsed_times)
            if ntimes:
                task.mean_elapsed_time = sum(tdef.elapsed_times) / ntimes
            elif tdef.rtconfig['job']['execution time limit']:
                task.mean_elapsed_time = \
                    tdef.rtconfig['job']['execution time limit']
            tasks[name] = task

        # family definition data objects creation
        for name in ancestors.keys():
            if name in config.taskdefs.keys():
                continue
            f_id = f"{self.workflow_id}/{name}"
            f_check = f"{name}@{update_time}"
            family = PbFamily(
                checksum=f_check,
                id=f_id,
                name=name,
                depth=len(ancestors[name]) - 1,
            )
            famcfg = config.cfg['runtime'][name]
            for key, val in famcfg.get('meta', {}).items():
                if key in ['title', 'description', 'url']:
                    setattr(family.meta, key, val)
                else:
                    family.meta.user_defined.append(f"{key}={val}")
            family.parents.extend(
                [f"{self.workflow_id}/{p_name}"
                    for p_name in parents[name]])
            families[name] = family

        for name, parent_list in parents.items():
            if parent_list and parent_list[0] in families:
                ch_id = f"{self.workflow_id}/{name}"
                if name in config.taskdefs:
                    families[parent_list[0]].child_tasks.append(ch_id)
                else:
                    families[parent_list[0]].child_families.append(ch_id)

        workflow.api_version = self.schd.server.API
        workflow.cylc_version = CYLC_VERSION
        workflow.name = self.schd.suite
        workflow.owner = self.schd.owner
        workflow.host = self.schd.host
        workflow.port = self.schd.port
        for key, val in config.cfg['meta'].items():
            if key in ['title', 'description', 'URL']:
                setattr(workflow.meta, key, val)
            else:
                workflow.meta.user_defined.append(f"{key}={val}")
        workflow.tree_depth = max(
            [len(val) for key, val in ancestors.items()]) - 1

        if get_utc_mode():
            time_zone_info = TIME_ZONE_UTC_INFO
        else:
            time_zone_info = TIME_ZONE_LOCAL_INFO
        for key, val in time_zone_info.items():
            setattr(workflow.time_zone_info, key, val)

        workflow.last_updated = update_time
        workflow.run_mode = config.run_mode()
        workflow.cycling_mode = config.cfg['scheduling']['cycling mode']
        workflow.workflow_log_dir = self.schd.suite_log_dir
        workflow.job_log_names.extend(list(JOB_LOG_OPTS.values()))
        workflow.ns_defn_order.extend(config.ns_defn_order)

        workflow.tasks.extend([t.id for t in tasks.values()])
        workflow.families.extend([f.id for f in families.values()])

        # replace the originals (atomic update, for access from other threads).
        self.ancestors = ancestors
        self.descendants = descendants
        self.parents = parents
        self.tasks = tasks
        self.families = families
        self.workflow = workflow

    def _generate_ghost_task(self, task_id):
        """Create task instances populated with static data fields."""
        update_time = time()

        name, point_string = TaskID.split(task_id)
        self.cycle_states.setdefault(point_string, {})[name] = None
        tp_id = f"{self.workflow_id}/{point_string}/{name}"
        tp_check = f"{task_id}@{update_time}"
        taskdef = self.tasks[name]
        tproxy = PbTaskProxy(
            checksum=tp_check,
            id=tp_id,
            task=taskdef.id,
            cycle_point=point_string,
            depth=taskdef.depth,
        )
        tproxy.namespace[:] = taskdef.namespace
        tproxy.parents[:] = [
            f"{self.workflow_id}/{point_string}/{p_name}"
            for p_name in self.parents[name]]
        p1_name = self.parents[name][0]
        tproxy.first_parent = f"{self.workflow_id}/{point_string}/{p1_name}"
        return tproxy

    def _generate_ghost_families(self, family_proxies=None, cycle_points=None):
        """Generate the family proxies from tasks in cycle points."""
        update_time = time()
        if family_proxies is None:
            family_proxies = {}
        fam_proxy_ids = {}
        for point_string, tasks in self.cycle_states.items():
            # construct family tree based on the
            # first-parent single-inheritance tree
            if not cycle_points or point_string not in cycle_points:
                continue
            cycle_first_parents = set([])

            for key in tasks:
                for parent in self.ancestors.get(key, []):
                    if parent == key:
                        continue
                    cycle_first_parents.add(parent)

            for fam in cycle_first_parents:
                if fam not in self.families:
                    continue
                int_id = TaskID.get(fam, point_string)
                fp_id = f"{self.workflow_id}/{point_string}/{fam}"
                fp_check = f"{int_id}@{update_time}"
                fproxy = PbFamilyProxy(
                    checksum=fp_check,
                    id=fp_id,
                    cycle_point=point_string,
                    name=fam,
                    family=f"{self.workflow_id}/{fam}",
                    depth=self.families[fam].depth,
                )
                for child_name in self.descendants[fam]:
                    ch_id = f"{self.workflow_id}/{point_string}/{child_name}"
                    if self.parents[child_name][0] == fam:
                        if child_name in cycle_first_parents:
                            fproxy.child_families.append(ch_id)
                        elif child_name in self.tasks:
                            fproxy.child_tasks.append(ch_id)
                if self.parents[fam]:
                    fproxy.parents.extend(
                        [f"{self.workflow_id}/{point_string}/{p_name}"
                            for p_name in self.parents[fam]])
                    p1_name = self.parents[fam][0]
                    fproxy.first_parent = (
                        f"{self.workflow_id}/{point_string}/{p1_name}")
                family_proxies[int_id] = fproxy
                fam_proxy_ids.setdefault(fam, []).append(fp_id)
        self.family_proxies = family_proxies
        for fam, ids in fam_proxy_ids.items():
            self.families[fam].proxies[:] = ids

    def generate_graph_elements(self, edges=None, graph=None,
                                task_proxies=None, family_proxies=None,
                                start_point=None, stop_point=None):
        """Generate edges and ghost nodes (proxy elements)."""
        config = self.schd.config
        if edges is None:
            edges = {}
        if graph is None:
            graph = PbEdges()
        if task_proxies is None:
            task_proxies = {}
        if family_proxies is None:
            family_proxies = {}
        if start_point is None:
            start_point = str(self.schd.pool.get_min_point() or '')
        if stop_point is None:
            stop_point = str(self.schd.pool.get_max_point() or '')

        cycle_points = set([])

        # Generate ungrouped edges
        try:
            graph_edges = config.get_graph_edges(start_point, stop_point)
        except TypeError:
            graph_edges = []

        if graph_edges:
            for e_list in graph_edges:
                # Reference or create edge source & target nodes/proxies
                s_node = e_list[0]
                t_node = e_list[1]
                if s_node is None:
                    continue
                else:
                    name, point = TaskID.split(s_node)
                    if name not in self.tasks:
                        continue
                    cycle_points.add(point)
                    if s_node not in task_proxies:
                        task_proxies[s_node] = (
                            self._generate_ghost_task(s_node))
                    source_id = task_proxies[s_node].id
                    if source_id not in self.tasks[name].proxies:
                        self.tasks[name].proxies.append(source_id)
                if t_node:
                    if t_node not in task_proxies:
                        task_proxies[t_node] = (
                            self._generate_ghost_task(t_node))
                    target_id = task_proxies[t_node].id
                e_id = s_node + '/' + (t_node or 'NoTargetNode')
                edges[e_id] = PbEdge(
                    id=f"{self.workflow_id}/{e_id}",
                    source=source_id,
                    suicide=e_list[3],
                    cond=e_list[4],
                )
                if t_node:
                    edges[e_id].target = target_id
            graph.edges.extend([e.id for e in edges.values()])
            graph.leaves.extend(config.leaves)
            graph.feet.extend(config.feet)
            for key, info in config.suite_polling_tasks.items():
                graph.workflow_polling_tasks.add(
                    local_proxy=key,
                    workflow=info[0],
                    remote_proxy=info[1],
                    req_state=info[2],
                    graph_string=info[3],
                )

        self._generate_ghost_families(family_proxies, cycle_points)
        self.workflow.edges.CopyFrom(graph)
        # Replace the originals (atomic update, for access from other threads).
        self.task_proxies = task_proxies
        self.edges = edges
        self.graph = graph

    def update_task_proxies(self, task_ids=None):
        """Update dynamic task instance fields"""
        update_time = time()

        # update task instance
        for itask in self.schd.pool.get_all_tasks():
            name, point_string = TaskID.split(itask.identity)
            if ((task_ids and itask.identity not in task_ids) or
                    (itask.identity not in self.task_proxies)):
                continue
            ts = itask.get_state_summary()
            self.cycle_states.setdefault(point_string, {})[name] = ts['state']
            tproxy = self.task_proxies[itask.identity]
            tproxy.checksum = f"{itask.identity}@{update_time}"
            tproxy.state = ts['state']
            tproxy.job_submits = ts['submit_num']
            tproxy.spawned = ast.literal_eval(ts['spawned'])
            tproxy.latest_message = ts['latest_message']
            tproxy.jobs[:] = [
                f"{self.workflow_id}/{job_id}" for job_id in itask.jobs]
            tproxy.broadcasts[:] = [
                f"{key}={val}" for key, val in
                self.schd.task_events_mgr.broadcast_mgr.get_broadcast(
                    itask.identity).items()]
            prereq_list = []
            for prereq in itask.state.prerequisites:
                # Protobuf messages populated within
                prereq_obj = prereq.api_dump(self.workflow_id)
                if prereq_obj:
                    prereq_list.append(prereq_obj)
            tproxy.prerequisites.extend(prereq_list)
            for _, msg, is_completed in itask.state.outputs.get_all():
                tproxy.outputs.append(f"{msg}={is_completed}")

    def update_family_proxies(self, cycle_points=None):
        """Update state of family proxies"""
        update_time = time()

        # Compute state_counts (total, and per cycle).
        all_states = []
        state_count_cycles = {}

        for point_string, c_task_states in self.cycle_states.items():
            # For each cycle point, construct a family state tree
            # based on the first-parent single-inheritance tree
            if cycle_points and point_string not in cycle_points:
                continue
            c_fam_task_states = {}
            count = {}

            for key in c_task_states:
                state = c_task_states[key]
                if state is None:
                    continue
                try:
                    count[state] += 1
                except KeyError:
                    count[state] = 1

                all_states.append(state)
                for parent in self.ancestors.get(key, []):
                    if parent == key:
                        continue
                    c_fam_task_states.setdefault(parent, set([]))
                    c_fam_task_states[parent].add(state)

            state_count_cycles[point_string] = count

            for fam, child_states in c_fam_task_states.items():
                state = extract_group_state(child_states)
                int_id = TaskID.get(fam, point_string)
                if state is None or int_id not in self.family_proxies:
                    continue
                fproxy = self.family_proxies[int_id]
                fproxy.checksum = f"{int_id}@{update_time}"
                fproxy.state = state

        self.all_states = all_states
        self.state_count_cycles = state_count_cycles

    def update_workflow(self):
        """Update dynamic content of workflow."""
        update_time = time()
        workflow = deepcopy(self.workflow)
        workflow.checksum = f"{self.workflow_id}@{update_time}"
        state_count_totals = {}
        for _, count in list(self.state_count_cycles.items()):
            for state, state_count in count.items():
                state_count_totals.setdefault(state, 0)
                state_count_totals[state] += state_count
        for state, count in state_count_totals.items():
            setattr(workflow.state_totals,
                    copy(state).replace('-', '_'), count)

        for key, value in (
                ('oldest_cycle_point', self.schd.pool.get_min_point()),
                ('newest_cycle_point', self.schd.pool.get_max_point()),
                ('newest_runahead_cycle_point',
                    self.schd.pool.get_max_point_runahead())):
            if value:
                setattr(workflow, key, str(value))
            else:
                setattr(workflow, key, '')

        workflow.last_updated = update_time
        workflow.states.extend(list(set(self.all_states)).sort())
        workflow.reloading = self.schd.pool.do_reload

        # Construct a workflow status string for use by monitoring clients.
        if self.schd.pool.is_held:
            status_string = SUITE_STATUS_HELD
        elif self.schd.stop_mode is not None:
            status_string = SUITE_STATUS_STOPPING
        elif self.schd.pool.hold_point:
            status_string = (
                SUITE_STATUS_RUNNING_TO_HOLD %
                self.schd.pool.hold_point)
        elif self.schd.pool.stop_point:
            status_string = (
                SUITE_STATUS_RUNNING_TO_STOP %
                self.schd.pool.stop_point)
        elif self.schd.stop_clock_time is not None:
            status_string = (
                SUITE_STATUS_RUNNING_TO_STOP %
                self.schd.stop_clock_time_string)
        elif self.schd.stop_task:
            status_string = (
                SUITE_STATUS_RUNNING_TO_STOP %
                self.schd.stop_task)
        elif self.schd.config.final_point:
            status_string = (
                SUITE_STATUS_RUNNING_TO_STOP %
                self.schd.config.final_point)
        else:
            status_string = SUITE_STATUS_RUNNING
        workflow.status = status_string

        workflow.task_proxies[:] = [
            t.id for t in self.task_proxies.values()]
        workflow.family_proxies[:] = [
            f.id for f in self.family_proxies.values()]

        # Replace the originals (atomic update, for access from other threads).
        self.workflow = workflow

    def get_entire_workflow(self):
        workflow_msg = PbEntireWorkflow()
        workflow_msg.workflow.CopyFrom(self.workflow)
        workflow_msg.tasks.extend(list(self.tasks.values()))
        workflow_msg.task_proxies.extend(list(self.task_proxies.values()))
        workflow_msg.jobs.extend(list(self.schd.job_pool.pool.values()))
        workflow_msg.families.extend(list(self.families.values()))
        workflow_msg.family_proxies.extend(list(self.family_proxies.values()))
        workflow_msg.edges.extend(list(self.edges.values()))

        return workflow_msg

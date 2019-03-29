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
from copy import copy
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
        self.tasks = {}
        self.task_proxies = {}
        self.task_states = {}
        self.families = {}
        self.family_proxies = {}
        self.state_count_totals = {}
        self.state_count_cycles = {}
        self.edges = {}
        self.graph = PbEdges()
        self.workflow_id = f"{self.schd.owner}/{self.schd.suite}"
        self.workflow = PbWorkflow()

    def initiate_data_model(self):
        """Initiate or Update data model."""
        update_time = time()
        config = self.schd.config
        tasks = {}
        task_proxies = {}
        families = {}
        family_proxies = {}
        edges = {}
        graph = PbEdges()
        workflow = PbWorkflow(
            checksum=f"{self.workflow_id}@{update_time}",
            id=self.workflow_id,
        )

        all_states = []

        # Compute state_counts (total, and per cycle).
        state_count_totals = {}
        state_count_cycles = {}

        ancestors_dict = config.get_first_parent_ancestors()
        descendants_dict = config.get_first_parent_descendants()
        parents_dict = config.get_parent_lists()

        # create task definition data objects
        for name, tdef in config.taskdefs.items():
            t_id = f"{self.workflow_id}/{name}"
            t_check = f"{name}@{update_time}"
            task = PbTask(
                checksum=t_check,
                id=t_id,
                name=name,
                depth=len(ancestors_dict[name]) - 1,
            )
            task.namespace.extend(copy(tdef.namespace_hierarchy))
            for key, val in dict(tdef.describe()).items():
                if key in ['title', 'description', 'URL']:
                    setattr(task.meta, key, val)
                else:
                    task.meta.user_defined.append(f"{key}={val}")
            ntimes = len(tdef.elapsed_times)
            if ntimes:
                task.mean_elapsed_time = (
                    float(sum(tdef.elapsed_times)) / ntimes)
            elif tdef.rtconfig['job']['execution time limit']:
                task.mean_elapsed_time = \
                    tdef.rtconfig['job']['execution time limit']
            tasks[name] = task

        # create task definition data objects
        for itask in self.schd.pool.get_all_tasks():
            ts = itask.get_state_summary()
            name, point_string = TaskID.split(itask.identity)
            if name not in tasks:
                continue
            # legacy, but still used here..
            self.task_states.setdefault(point_string, {})
            self.task_states[point_string][name] = ts['state']
            # graphql new:
            tp_id = f"{self.workflow_id}/{point_string}/{name}"
            tp_check = f"{itask.identity}@{update_time}"
            tasks[name].proxies.append(tp_id)
            tproxy = PbTaskProxy(
                checksum=tp_check,
                id=tp_id,
                task=tasks[name].id,
                state=ts['state'],
                cycle_point=point_string,
                job_submits=ts['submit_num'],
                spawned=ast.literal_eval(ts['spawned']),
                latest_message=ts['latest_message'],
                depth=len(ancestors_dict[name]) - 1,
            )
            tproxy.jobs.extend(
                [f"{self.workflow_id}/{job_id}" for job_id in itask.jobs])
            tproxy.namespace.extend(
                [p_name for p_name in itask.tdef.namespace_hierarchy])
            tproxy.proxy_namespace.extend(
                [f"{self.workflow_id}/{point_string}/{p_name}"
                    for p_name in itask.tdef.namespace_hierarchy])
            tproxy.parents.extend(
                [f"{self.workflow_id}/{point_string}/{p_name}"
                    for p_name in parents_dict[name]])
            tproxy.broadcasts.extend(
                [f"{key}={val}" for key, val in
                    self.schd.task_events_mgr.broadcast_mgr.get_broadcast(
                        itask.identity).items()])
            prereq_list = []
            for prereq in itask.state.prerequisites:
                # Protobuf messages populated within
                prereq_obj = prereq.api_dump(self.workflow_id)
                if prereq_obj:
                    prereq_list.append(prereq_obj)
            tproxy.prerequisites.extend(prereq_list)
            for _, msg, is_completed in itask.state.outputs.get_all():
                tproxy.outputs.append(f"{msg}={is_completed}")

            task_proxies[itask.identity] = tproxy

        # Family definition data objects creation
        for name in ancestors_dict.keys():
            if name in config.taskdefs.keys():
                continue
            f_id = f"{self.workflow_id}/{name}"
            f_check = f"{name}@{update_time}"
            family = PbFamily(
                checksum=f_check,
                id=f_id,
                name=name,
                depth=len(ancestors_dict[name]) - 1,
            )
            famcfg = config.cfg['runtime'][name]
            for key, val in famcfg.get('meta', {}).items():
                if key in ['title', 'description', 'URL']:
                    setattr(family.meta, key, val)
                else:
                    family.meta.user_defined.append(f"{key}={val}")
            family.parents.extend(
                [f"{self.workflow_id}/{p_name}"
                    for p_name in parents_dict[name]])
            families[name] = family

        for name, parent_list in parents_dict.items():
            if parent_list and parent_list[0] in families:
                if name in config.taskdefs:
                    families[parent_list[0]].child_tasks.append(name)
                else:
                    families[parent_list[0]].child_families.append(name)

        for point_string, c_task_states in self.task_states.items():
            # For each cycle point, construct a family state tree
            # based on the first-parent single-inheritance tree

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
                for parent in ancestors_dict.get(key, []):
                    if parent == key:
                        continue
                    c_fam_task_states.setdefault(parent, set([]))
                    c_fam_task_states[parent].add(state)

            state_count_cycles[point_string] = count

            for fam, child_states in c_fam_task_states.items():
                state = extract_group_state(child_states)
                if state is None or fam not in families:
                    continue
                int_id = TaskID.get(fam, point_string)
                fp_id = f"{self.workflow_id}/{point_string}/{fam}"
                fp_check = f"{int_id}@{update_time}"
                families[fam].proxies.append(fp_id)
                fproxy = PbFamilyProxy(
                    checksum=fp_check,
                    id=fp_id,
                    cycle_point=point_string,
                    name=fam,
                    family=f"{self.workflow_id}/{fam}",
                    state=state,
                    depth=len(ancestors_dict[fam]) - 1,
                )
                for child_name in descendants_dict[fam]:
                    ch_id = f"{self.workflow_id}/{point_string}/{child_name}"
                    if parents_dict[child_name][0] == fam:
                        if child_name in c_fam_task_states:
                            fproxy.child_families.append(ch_id)
                        else:
                            fproxy.child_tasks.append(ch_id)
                fproxy.parents.extend(
                    [f"{self.workflow_id}/{point_string}/{p_name}"
                        for p_name in parents_dict[name]])
                family_proxies[int_id] = fproxy

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
            [len(val) for key, val in ancestors_dict.items()]) - 1

        state_count_totals = {}
        for point_string, count in list(state_count_cycles.items()):
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

        if get_utc_mode():
            time_zone_info = TIME_ZONE_UTC_INFO
        else:
            time_zone_info = TIME_ZONE_LOCAL_INFO
        for key, val in time_zone_info.items():
            setattr(workflow.time_zone_info, key, val)

        workflow.last_updated = update_time
        workflow.run_mode = self.schd.run_mode
        workflow.cycling_mode = config.cfg['scheduling']['cycling mode']
        workflow.states.extend(list(set(all_states)).sort())
        workflow.reloading = self.schd.pool.do_reload
        workflow.workflow_log_dir = self.schd.suite_log_dir
        workflow.job_log_names.extend(list(JOB_LOG_OPTS.values()))
        workflow.ns_defn_order.extend(config.ns_defn_order)

        # Construct a workflow status string for use by monitoring clients.
        if self.schd.pool.is_held:
            status_string = SUITE_STATUS_HELD
        elif self.schd.stop_mode is not None:
            status_string = SUITE_STATUS_STOPPING
        elif self.schd.pool.hold_point:
            status_string = (
                SUITE_STATUS_RUNNING_TO_HOLD %
                self.schd.pool.hold_point)
        elif self.schd.stop_point:
            status_string = (
                SUITE_STATUS_RUNNING_TO_STOP %
                self.schd.stop_point)
        elif self.schd.stop_clock_time is not None:
            status_string = (
                SUITE_STATUS_RUNNING_TO_STOP %
                self.schd.stop_clock_time_string)
        elif self.schd.stop_task:
            status_string = (
                SUITE_STATUS_RUNNING_TO_STOP %
                self.schd.stop_task)
        elif self.schd.final_point:
            status_string = (
                SUITE_STATUS_RUNNING_TO_STOP %
                self.schd.final_point)
        else:
            status_string = SUITE_STATUS_RUNNING
        workflow.status = status_string

        workflow.tasks.extend([t.id for t in tasks.values()])
        workflow.families.extend([f.id for f in families.values()])

        # Generate ungrouped edges
        try:
            graph_edges = config.get_graph_edges(
                workflow.oldest_cycle_point,
                workflow.newest_cycle_point,
                group_nodes=None, ungroup_nodes=None,
                ungroup_recursive=False, group_all=False
            )
        except TypeError:
            graph_edges = []

        if isinstance(graph_edges, list) and graph_edges != []:
            for e_list in graph_edges:
                if e_list[0] is None:
                    continue
                elif e_list[0] in task_proxies:
                    t_node = task_proxies[e_list[0]].id
                else:
                    tn_name, tn_point = TaskID.split(e_list[0])
                    t_node = f"{self.workflow_id}/{tn_point}/{tn_name}"
                if e_list[1] is None:
                    h_node = f"{self.workflow_id}/None"
                elif e_list[1] in task_proxies:
                    h_node = task_proxies[e_list[1]].id
                else:
                    hn_name, hn_point = TaskID.split(e_list[1])
                    h_node = f"{self.workflow_id}/{hn_point}/{hn_name}"
                e_id = e_list[0] + '/' + (e_list[1] or 'None')
                edges[e_id] = PbEdge(
                    id=f"{self.workflow_id}/{e_id}",
                    tail_node=t_node,
                    head_node=h_node,
                    suicide=e_list[3],
                    cond=e_list[4],
                )
            graph.edges.extend([e.id for e in edges.values()])
            graph.leaves.extend(config.leaves)
            graph.feet.extend(config.feet)
            workflow.edges.CopyFrom(self.graph)
            for key, info in config.suite_polling_tasks.items():
                graph.workflow_polling_tasks.add(
                    local_proxy=key,
                    workflow=info[0],
                    remote_proxy=info[1],
                    req_state=info[2],
                    graph_string=info[3],
                )

        # Replace the originals (atomic update, for access from other threads).
        self.state_count_totals = state_count_totals
        self.state_count_cycles = state_count_cycles
        self.tasks = tasks
        self.task_proxies = task_proxies
        self.families = families
        self.family_proxies = family_proxies
        self.edges = edges
        self.graph = graph
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

        return workflow_msg.SerializeToString()

#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
"""Manage suite state summary for client, e.g. GUI."""

from time import time

from cylc.task_id import TaskID
from cylc.wallclock import (
    TIME_ZONE_LOCAL_INFO, TIME_ZONE_UTC_INFO, get_utc_mode)
from cylc.suite_status import (
    SUITE_STATUS_HELD, SUITE_STATUS_STOPPING,
    SUITE_STATUS_RUNNING, SUITE_STATUS_RUNNING_TO_STOP,
    SUITE_STATUS_RUNNING_TO_HOLD)
from cylc.task_state import TASK_STATUS_RUNAHEAD
from cylc.task_state_prop import extract_group_state

from cylc.network.schema import QLPrereq, QLJobHost, QLOutputs, QLTask, QLFamily


class StateSummaryMgr(object):
    """Manage suite state summary for client, e.g. GUI."""

    TIME_FIELDS = ['submitted_time', 'started_time', 'finished_time']

    def __init__(self):
        self.task_summary = {}
        self.global_summary = {}
        self.family_summary = {}
        self.update_time = None
        self.state_count_totals = {}
        self.state_count_cycles = {}

        self.taskql_data = {}
        self.familyql_data = {}
        self.globalql_data = {}

    def update(self, schd):
        """Update."""
        self.update_time = time()
        global_summary = {}
        family_summary = {}
        familyql_data = {}
        globalql_data = {}

        task_summary, task_states, taskql_data = self._get_tasks_info(schd)

        all_states = []
        ancestors_dict = schd.config.get_first_parent_ancestors()
        descendants_dict = schd.config.get_first_parent_descendants()
        parents_dict = schd.config.get_parent_lists()

        # Compute state_counts (total, and per cycle).
        state_count_totals = {}
        state_count_cycles = {}

        for point_string, c_task_states in task_states.items():
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
                f_id = TaskID.get(fam, point_string)
                state = extract_group_state(child_states)
                if state is None:
                    continue
                try:
                    famcfg = schd.config.cfg['runtime'][fam]['meta']
                except KeyError:
                    famcfg = {}
                description = famcfg.get('description')
                title = famcfg.get('title')
                url = famcfg.get('URL')
                family_summary[f_id] = {'name': fam,
                                        'description': description,
                                        'title': title,
                                        'label': point_string,
                                        'state': state}
                #familyql specific
                famparents = [TaskID.get(
                    pname, point_string) for pname in parents_dict[fam]]
                taskdescs = []
                famdescs = []
                for desc_name in descendants_dict[fam]:
                    if parents_dict[desc_name][0] == fam:
                        if desc_name in c_fam_task_states:
                            famdescs.append(
                                TaskID.get(desc_name, point_string))
                        else:
                            taskdescs.append(
                                TaskID.get(desc_name, point_string))

                familyql_data[f_id] = QLFamily(
                    id = f_id,
                    name = fam,
                    label = point_string,
                    state = state,
                    title = title,
                    description = description,
                    URL = url,
                    parents = famparents,
                    tasks = taskdescs,
                    families = famdescs
                )


        globalql_data['title'] = schd.config.cfg['meta']['title']
        globalql_data['description'] = schd.config.cfg['meta']['description']
        globalql_data['group'] = schd.config.cfg['meta']['group']
        globalql_data['url'] = schd.config.cfg['meta']['URL']

        state_count_totals = {}
        for point_string, count in state_count_cycles.items():
            for state, state_count in count.items():
                state_count_totals.setdefault(state, 0)
                state_count_totals[state] += state_count

        all_states.sort()

        for key1, key2, value in (
                ('oldest cycle point string', 'oldest_cycle_point',
                    schd.pool.get_min_point()),
                ('newest cycle point string', 'newest_cycle_point',
                    schd.pool.get_max_point()),
                ('newest runahead cycle point string',
                    'newest_runahead_cycle_point',
                    schd.pool.get_max_point_runahead())):
            if value:
                global_summary[key1] = str(value)
                globalql_data[key2] = str(value)
            else:
                global_summary[key1] = None
                globalql_data[key2] = None

        if get_utc_mode():
            global_summary['time zone info'] = TIME_ZONE_UTC_INFO
            globalql_data['time_zone_info'] = TIME_ZONE_UTC_INFO
        else:
            global_summary['time zone info'] = TIME_ZONE_LOCAL_INFO
            globalql_data['time_zone_info'] = TIME_ZONE_LOCAL_INFO
        global_summary['last_updated'] = self.update_time
        global_summary['run_mode'] = schd.run_mode
        global_summary['states'] = all_states
        global_summary['namespace definition order'] = (
            schd.config.ns_defn_order)
        global_summary['reloading'] = schd.pool.do_reload
        global_summary['state totals'] = state_count_totals

        globalql_data['last_updated'] = self.update_time
        globalql_data['run_mode'] = schd.run_mode
        globalql_data['states'] = all_states
        globalql_data['namespace_definition_order'] = (
            schd.config.ns_defn_order)
        globalql_data['reloading'] = schd.pool.do_reload
        globalql_data['state_totals'] = state_count_totals

        # Extract suite and task URLs from config.
        global_summary['suite_urls'] = dict(
            (i, j['meta']['URL'])
            for (i, j) in schd.config.cfg['runtime'].items())
        global_summary['suite_urls']['suite'] = schd.config.cfg['meta']['URL']

        # Construct a suite status string for use by monitoring clients.
        if schd.pool.is_held:
            status_string = SUITE_STATUS_HELD
        elif schd.stop_mode is not None:
            status_string = SUITE_STATUS_STOPPING
        elif schd.pool.hold_point:
            status_string = (
                SUITE_STATUS_RUNNING_TO_HOLD % schd.pool.hold_point)
        elif schd.stop_point:
            status_string = (SUITE_STATUS_RUNNING_TO_STOP % schd.stop_point)
        elif schd.stop_clock_time is not None:
            status_string = (
                SUITE_STATUS_RUNNING_TO_STOP % schd.stop_clock_time_string)
        elif schd.stop_task:
            status_string = (SUITE_STATUS_RUNNING_TO_STOP % schd.stop_task)
        elif schd.final_point:
            status_string = (SUITE_STATUS_RUNNING_TO_STOP % schd.final_point)
        else:
            status_string = SUITE_STATUS_RUNNING
        
        global_summary['status_string'] = status_string
        globalql_data['status'] = status_string

        # Replace the originals (atomic update, for access from other threads).
        self.task_summary = task_summary
        self.global_summary = global_summary
        self.family_summary = family_summary
        self.state_count_totals = state_count_totals
        self.state_count_cycles = state_count_cycles
        self.taskql_data = taskql_data
        self.familyql_data = familyql_data
        self.globalql_data = globalql_data

    @staticmethod
    def _get_tasks_info(schd):
        """Retrieve task summary info and states."""

        task_summary = {}
        task_states = {}
        taskql_data = {}
        parents_dict = schd.config.get_parent_lists()

        for task in schd.pool.get_tasks():
            ts = task.get_state_summary()
            task_summary[task.identity] = ts
            name, point_string = TaskID.split(task.identity)
            task_states.setdefault(point_string, {})
            task_states[point_string][name] = ts['state']
            #taskql specific:
            task_parents = [TaskID.get(
                pname, point_string) for pname in parents_dict[name]]
            j_hosts = [] 
            for key in ts['job_hosts']:
                jhost = QLJobHost(
                    submit_num = key,
                    job_host = ts['job_hosts'][key])
                j_hosts.append(jhost)

            taskmeta = task.tdef.describe()
            t_outs = QLOutputs()
            for _, msg, is_completed in task.state.outputs.get_all():
                if msg == 'submit-failed':
                    msg = 'submit_failed'
                setattr(t_outs, msg, is_completed)
     
            prereq_list = [] 
            for item in task.state.prerequisites_dump():
                t_prereq = QLPrereq(condition = item[0], message = item[1])
                prereq_list.append(t_prereq)

            taskql_data[task.identity] = QLTask(
                id = task.identity,
                name = name,
                label = point_string,
                state = ts['state'],
                title = ts['title'],
                description = ts['description'],
                URL = taskmeta['URL'],
                parents = task_parents,
                spawned = ts['spawned'],
                execution_time_limit = ts['execution_time_limit'],
                submitted_time = ts['submitted_time'],
                started_time = ts['started_time'],
                finished_time = ts['finished_time'],
                mean_elapsed_time = ts['mean_elapsed_time'],
                submitted_time_string = ts['submitted_time_string'],
                started_time_string = ts['started_time_string'],
                finished_time_string = ts['finished_time_string'],
                host = task.task_host,
                batch_sys_name = ts['batch_sys_name'],
                submit_method_id = ts['submit_method_id'],
                submit_num = ts['submit_num'],
                namespace = task.tdef.namespace_hierarchy,
                logfiles = ts['logfiles'],
                latest_message = ts['latest_message'],
                job_hosts = j_hosts,
                prerequisites = prereq_list,
                outputs = t_outs)


        for task in schd.pool.get_rh_tasks():
            ts = task.get_state_summary()
            ts['state'] = TASK_STATUS_RUNAHEAD
            task_summary[task.identity] = ts
            name, point_string = TaskID.split(task.identity)
            task_states.setdefault(point_string, {})
            task_states[point_string][name] = ts['state']
            #taskql specific:
            task_parents = [TaskID.get(
                pname, point_string) for pname in parents_dict[name]]
            j_hosts = [] 
            for key in ts['job_hosts']:
                jhost = QLJobHost(
                    submit_num = key,
                    job_host = ts['job_hosts'][key])
                j_hosts.append(jhost)

            taskmeta = task.tdef.describe()
            t_outs = QLOutputs()
            for _, msg, is_completed in task.state.outputs.get_all():
                if msg == 'submit-failed':
                    msg = 'submit_failed'
                setattr(t_outs, msg, is_completed)
     
            prereq_list = [] 
            for item in task.state.prerequisites_dump():
                t_prereq = QLPrereq(condition = item[0], message = item[1])
                prereq_list.append(t_prereq)

            taskql_data[task.identity] = QLTask(
                id = task.identity,
                name = name,
                label = point_string,
                state = ts['state'],
                title = ts['title'],
                description = ts['description'],
                URL = taskmeta['URL'],
                parents = task_parents,
                spawned = ts['spawned'],
                execution_time_limit = ts['execution_time_limit'],
                submitted_time = ts['submitted_time'],
                started_time = ts['started_time'],
                finished_time = ts['finished_time'],
                mean_elapsed_time = ts['mean_elapsed_time'],
                submitted_time_string = ts['submitted_time_string'],
                started_time_string = ts['started_time_string'],
                finished_time_string = ts['finished_time_string'],
                host = task.task_host,
                batch_sys_name = ts['batch_sys_name'],
                submit_method_id = ts['submit_method_id'],
                submit_num = ts['submit_num'],
                namespace = task.tdef.namespace_hierarchy,
                logfiles = ts['logfiles'],
                latest_message = ts['latest_message'],
                job_hosts = j_hosts,
                prerequisites = prereq_list,
                outputs = t_outs)

        return task_summary, task_states, taskql_data


    def get_state_summary(self):
        """Return the global, task, and family summary data structures."""
        return (self.global_summary, self.task_summary, self.family_summary)

    def get_state_totals(self):
        """Return dict of count per state and dict of state count per cycle."""
        return (self.state_count_totals, self.state_count_cycles)

    def get_tasks_by_state(self):
        """Returns a dictionary containing lists of tasks by state in the form:
        {state: [(most_recent_time_string, task_name, point_string), ...]}."""
        # Get tasks.
        ret = {}
        for task in self.task_summary:
            state = self.task_summary[task]['state']
            if state not in ret:
                ret[state] = []
            times = [0]
            for time_field in self.TIME_FIELDS:
                if (time_field in self.task_summary[task] and
                        self.task_summary[task][time_field]):
                    times.append(self.task_summary[task][time_field])
            task_name, point_string = task.rsplit('.', 1)
            ret[state].append((max(times), task_name, point_string,))

        # Trim down to no more than six tasks per state.
        for state in ret:
            ret[state].sort(reverse=True)
            if len(ret[state]) < 7:
                ret[state] = ret[state][0:6]
            else:
                ret[state] = ret[state][0:5] + [
                    (None, len(ret[state]) - 5, None,)]

        return ret

    def get_taskql_data(self):
        """Return the task summary resource the GraphQL endpoint."""
        return self.taskql_data

    def get_familyql_data(self):
        """Return the family summary resource the GraphQL endpoint."""
        return self.familyql_data

    def get_globalql_data(self):
        """Return the global summary resource the GraphQL endpoint."""
        return self.globalql_data

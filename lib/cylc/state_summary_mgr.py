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
"""Manage suite state summary for client."""

from time import time

from cylc.task_id import TaskID
from cylc.suite_status import (
    SUITE_STATUS_HELD, SUITE_STATUS_STOPPING,
    SUITE_STATUS_RUNNING, SUITE_STATUS_RUNNING_TO_STOP,
    SUITE_STATUS_RUNNING_TO_HOLD)
from cylc.task_state import TASK_STATUS_RUNAHEAD
from cylc.task_state_prop import extract_group_state
from cylc.wallclock import (
    TIME_ZONE_LOCAL_INFO, TIME_ZONE_UTC_INFO, get_utc_mode)


class StateSummaryMgr(object):
    """Manage suite state summary for client."""

    TIME_FIELDS = ['submitted_time', 'started_time', 'finished_time']

    def __init__(self):
        self.task_summary = {}
        self.global_summary = {}
        self.family_summary = {}
        self.update_time = None
        self.state_count_totals = {}
        self.state_count_cycles = {}

    def update(self, schd):
        """Update."""
        self.update_time = time()
        global_summary = {}
        family_summary = {}

        task_summary, task_states = self._get_tasks_info(schd)

        all_states = []
        ancestors_dict = schd.config.get_first_parent_ancestors()

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
                family_summary[f_id] = {'name': fam,
                                        'description': description,
                                        'title': title,
                                        'label': point_string,
                                        'state': state}

        state_count_totals = {}
        for point_string, count in list(state_count_cycles.items()):
            for state, state_count in count.items():
                state_count_totals.setdefault(state, 0)
                state_count_totals[state] += state_count

        all_states.sort()

        for key, value in (
                ('oldest cycle point string', schd.pool.get_min_point()),
                ('newest cycle point string', schd.pool.get_max_point()),
                ('newest runahead cycle point string',
                 schd.pool.get_max_point_runahead())):
            if value:
                global_summary[key] = str(value)
            else:
                global_summary[key] = None
        if get_utc_mode():
            global_summary['time zone info'] = TIME_ZONE_UTC_INFO
        else:
            global_summary['time zone info'] = TIME_ZONE_LOCAL_INFO
        global_summary['last_updated'] = self.update_time
        global_summary['run_mode'] = schd.run_mode
        global_summary['states'] = all_states
        global_summary['namespace definition order'] = (
            schd.config.ns_defn_order)
        global_summary['reloading'] = schd.pool.do_reload
        global_summary['state totals'] = state_count_totals
        # Extract suite and task URLs from config.
        global_summary['suite_urls'] = dict(
            (i, j['meta']['URL'])
            for (i, j) in schd.config.cfg['runtime'].items())
        global_summary['suite_urls']['suite'] = schd.config.cfg['meta']['URL']

        # Construct a suite status string for use by monitoring clients.
        if schd.pool.is_held:
            global_summary['status_string'] = SUITE_STATUS_HELD
        elif schd.stop_mode is not None:
            global_summary['status_string'] = SUITE_STATUS_STOPPING
        elif schd.pool.hold_point:
            global_summary['status_string'] = (
                SUITE_STATUS_RUNNING_TO_HOLD % schd.pool.hold_point)
        elif schd.stop_point:
            global_summary['status_string'] = (
                SUITE_STATUS_RUNNING_TO_STOP % schd.stop_point)
        elif schd.stop_clock_time is not None:
            global_summary['status_string'] = (
                SUITE_STATUS_RUNNING_TO_STOP % schd.stop_clock_time_string)
        elif schd.stop_task:
            global_summary['status_string'] = (
                SUITE_STATUS_RUNNING_TO_STOP % schd.stop_task)
        elif schd.final_point:
            global_summary['status_string'] = (
                SUITE_STATUS_RUNNING_TO_STOP % schd.final_point)
        else:
            global_summary['status_string'] = SUITE_STATUS_RUNNING

        # Replace the originals (atomic update, for access from other threads).
        self.task_summary = task_summary
        self.global_summary = global_summary
        self.family_summary = family_summary
        self.state_count_totals = state_count_totals
        self.state_count_cycles = state_count_cycles

    @staticmethod
    def _get_tasks_info(schd):
        """Retrieve task summary info and states."""

        task_summary = {}
        task_states = {}

        for task in schd.pool.get_tasks():
            ts = task.get_state_summary()
            task_summary[task.identity] = ts
            name, point_string = TaskID.split(task.identity)
            task_states.setdefault(point_string, {})
            task_states[point_string][name] = ts['state']

        for task in schd.pool.get_rh_tasks():
            ts = task.get_state_summary()
            ts['state'] = TASK_STATUS_RUNAHEAD
            task_summary[task.identity] = ts
            name, point_string = TaskID.split(task.identity)
            task_states.setdefault(point_string, {})
            task_states[point_string][name] = ts['state']

        return task_summary, task_states

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

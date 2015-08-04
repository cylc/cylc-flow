#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

import time
import datetime

import cylc.flags
from cylc.task_id import TaskID
from cylc.wallclock import TIME_ZONE_LOCAL_INFO, TIME_ZONE_UTC_INFO
from cylc.config import SuiteConfig
from cylc.network import PYRO_STATE_OBJ_NAME
from cylc.network.pyro_base import PyroClient, PyroServer
from cylc.network import check_access_priv


class SuiteStillInitialisingError(Exception):
    """Exception raised if a summary is requested before the first update.

    This can happen if client connects during start-up for large suites.

    """
    def __str__(self):
        return "Suite initializing..."


class StateSummaryServer(PyroServer):
    """Server-side suite state summary interface."""

    _INSTANCE = None

    @classmethod
    def get_inst(cls, run_mode=None):
        """Return a singleton instance."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls(run_mode)
        return cls._INSTANCE

    def __init__(self, run_mode):
        super(StateSummaryServer, self).__init__()
        self.task_summary = {}
        self.global_summary = {}
        self.family_summary = {}
        self.run_mode = run_mode
        self.first_update_completed = False
        self._summary_update_time = None

        self.state_count_totals = {}
        self.state_count_cycles = {}

    def update(self, tasks, tasks_rh, min_point, max_point, max_point_rh,
               paused, will_pause_at, stopping, will_stop_at, ns_defn_order,
               reloading):
        task_summary = {}
        global_summary = {}
        family_summary = {}
        task_states = {}

        fs = None
        for tlist in [tasks, tasks_rh]:
            for task in tlist:
                ts = task.get_state_summary()
                if fs:
                    ts['state'] = fs
                task_summary[task.identity] = ts
                name, point_string = TaskID.split(task.identity)
                point_string = str(point_string)
                task_states.setdefault(point_string, {})
                task_states[point_string][name] = (
                    task_summary[task.identity]['state'])
            fs = 'runahead'

        fam_states = {}
        all_states = []
        for point_string, c_task_states in task_states.items():
            # For each cycle point, construct a family state tree
            # based on the first-parent single-inheritance tree

            c_fam_task_states = {}
            config = SuiteConfig.get_inst()

            for key, parent_list in (
                    config.get_first_parent_ancestors().items()):
                state = c_task_states.get(key)
                if state is None:
                    continue
                all_states.append(state)
                for parent in parent_list:
                    if parent == key:
                        continue
                    c_fam_task_states.setdefault(parent, [])
                    c_fam_task_states[parent].append(state)

            for fam, child_states in c_fam_task_states.items():
                f_id = TaskID.get(fam, point_string)
                state = extract_group_state(child_states)
                if state is None:
                    continue
                try:
                    famcfg = config.cfg['runtime'][fam]
                except KeyError:
                    famcfg = {}
                description = famcfg.get('description')
                title = famcfg.get('title')
                family_summary[f_id] = {'name': fam,
                                        'description': description,
                                        'title': title,
                                        'label': point_string,
                                        'state': state}

        all_states.sort()

        # Compute state_counts (total, and per cycle).
        state_count_totals = {}
        state_count_cycles = {}
        for point_string, name_states in task_states.items():
            count = {}
            for name, state in name_states.items():
                try:
                    count[state] += 1
                except KeyError:
                    count[state] = 1
                try:
                    state_count_totals[state] += 1
                except KeyError:
                    state_count_totals[state] = 1
            state_count_cycles[point_string] = count

        global_summary['oldest cycle point string'] = (
            self.str_or_None(min_point))
        global_summary['newest cycle point string'] = (
            self.str_or_None(max_point))
        global_summary['newest runahead cycle point string'] = (
            self.str_or_None(max_point_rh))
        if cylc.flags.utc:
            global_summary['daemon time zone info'] = TIME_ZONE_UTC_INFO
        else:
            global_summary['daemon time zone info'] = TIME_ZONE_LOCAL_INFO
        global_summary['last_updated'] = time.time()
        global_summary['run_mode'] = self.run_mode
        global_summary['paused'] = paused
        global_summary['stopping'] = stopping
        global_summary['will_pause_at'] = self.str_or_None(will_pause_at)
        global_summary['will_stop_at'] = self.str_or_None(will_stop_at)
        global_summary['states'] = all_states
        global_summary['namespace definition order'] = ns_defn_order
        global_summary['reloading'] = reloading
        global_summary['state totals'] = state_count_totals

        self._summary_update_time = time.time()

        # Replace the originals (atomic update, for access from other threads).
        self.task_summary = task_summary
        self.global_summary = global_summary
        self.family_summary = family_summary
        task_states = {}
        self.first_update_completed = True
        self.state_count_totals = state_count_totals
        self.state_count_cycles = state_count_cycles

    def str_or_None(self, s):
        if s:
            return str(s)
        else:
            return None

    def get_state_totals(self):
        # (Access to this is controlled via the suite_identity server.)
        return (self.state_count_totals, self.state_count_cycles)

    def get_state_summary(self):
        """Return the global, task, and family summary data structures."""
        check_access_priv(self, 'full-read')
        self.report('get_state_summary')
        if not self.first_update_completed:
            raise SuiteStillInitialisingError()
        return (self.global_summary, self.task_summary, self.family_summary)

    def get_summary_update_time(self):
        """Return the last time the summaries were changed (Unix time)."""
        check_access_priv(self, 'full-read')
        self.report('get_state_summary_update_time')
        if not self.first_update_completed:
            raise SuiteStillInitialisingError()
        return self._summary_update_time


class StateSummaryClient(PyroClient):
    """Client-side suite state summary interface."""

    target_server_object = PYRO_STATE_OBJ_NAME

    def get_suite_state_summary(self):
        return self.call_server_func("get_state_summary")

    def get_suite_state_summary_update_time(self):
        return self.call_server_func("get_summary_update_time")


def extract_group_state(child_states, is_stopped=False):
    """Summarise child states as a group."""

    ordered_states = ['submit-failed', 'failed', 'expired', 'submit-retrying',
                      'retrying', 'running', 'submitted', 'ready', 'queued',
                      'waiting', 'held', 'succeeded', 'runahead']
    if is_stopped:
        ordered_states = ['submit-failed', 'failed', 'running', 'submitted',
                          'expired', 'ready', 'submit-retrying', 'retrying',
                          'succeeded', 'queued', 'waiting', 'held', 'runahead']
    for state in ordered_states:
        if state in child_states:
            return state
    return None


def get_id_summary(id_, task_state_summary, fam_state_summary, id_family_map):
    """Return some state information about a task or family id."""
    prefix_text = ""
    meta_text = ""
    sub_text = ""
    sub_states = {}
    stack = [(id_, 0)]
    done_ids = []
    for summary in [task_state_summary, fam_state_summary]:
        if id_ in summary:
            title = summary[id_].get('title')
            if title:
                meta_text += "\n" + title.strip()
            description = summary[id_].get('description')
            if description:
                meta_text += "\n" + description.strip()
    while stack:
        this_id, depth = stack.pop(0)
        if this_id in done_ids:  # family dive down will give duplicates
            continue
        done_ids.append(this_id)
        prefix = "\n" + " " * 4 * depth + this_id
        if this_id in task_state_summary:
            submit_num = task_state_summary[this_id].get('submit_num')
            if submit_num:
                prefix += "(%02d)" % submit_num
            state = task_state_summary[this_id]['state']
            sub_text += prefix + " " + state
            sub_states.setdefault(state, 0)
            sub_states[state] += 1
        elif this_id in fam_state_summary:
            name, point_string = TaskID.split(this_id)
            sub_text += prefix + " " + fam_state_summary[this_id]['state']
            for child in reversed(sorted(id_family_map[name])):
                child_id = TaskID.get(child, point_string)
                stack.insert(0, (child_id, depth + 1))
        if not prefix_text:
            prefix_text = sub_text.strip()
            sub_text = ""
    if len(sub_text.splitlines()) > 10:
        state_items = sub_states.items()
        state_items.sort()
        state_items.sort(lambda x, y: cmp(y[1], x[1]))
        sub_text = ""
        for state, number in state_items:
            sub_text += "\n    {0} tasks {1}".format(number, state)
    if sub_text and meta_text:
        sub_text = "\n" + sub_text
    text = prefix_text + meta_text + sub_text
    if not text:
        return id_
    return text

#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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

import re
import time
import datetime

import cylc.flags
from cylc.task_id import TaskID
from cylc.wallclock import TIME_ZONE_LOCAL_INFO, TIME_ZONE_UTC_INFO
from cylc.config import SuiteConfig
from cylc.network import PYRO_STATE_OBJ_NAME
from cylc.network.pyro_base import PyroClient, PyroServer
from cylc.network import check_access_priv
from cylc.task_state import (
    TASK_STATUS_RUNAHEAD, TASK_STATUS_HELD, TASK_STATUS_WAITING,
    TASK_STATUS_EXPIRED, TASK_STATUS_QUEUED, TASK_STATUS_READY,
    TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED, TASK_STATUS_RETRYING)


# Suite status strings.
SUITE_STATUS_HELD = "held"
SUITE_STATUS_RUNNING = "running"
SUITE_STATUS_STOPPING = "stopping"
SUITE_STATUS_RUNNING_TO_STOP = "running to stop at %s"
SUITE_STATUS_RUNNING_TO_HOLD = "running to hold at %s"
# Regex to extract the stop or hold point.
SUITE_STATUS_SPLIT_REC = re.compile('^([a-z ]+ at )(.*)$')

# Pseudo status strings for use by suite monitors.
#   Use before attempting to determine status:
SUITE_STATUS_NOT_CONNECTED = "not connected"
#   Use prior to first status update:
SUITE_STATUS_CONNECTED = "connected"
SUITE_STATUS_INITIALISING = "initialising"
#   Use when the suite is not running:
SUITE_STATUS_STOPPED = "stopped"
SUITE_STATUS_STOPPED_WITH = "stopped with '%s'"


def get_suite_status_string(paused, stopping, will_pause_at, will_stop_at):
    """Construct a suite status summary string for client programs.

    This is in a function for re-use in monitor and GUI back-compat code
    (clients at cylc version <= 6.9.1 construct their own status string).

    """
    if paused:
        return SUITE_STATUS_HELD
    elif stopping:
        return SUITE_STATUS_STOPPING
    elif will_pause_at:
        return SUITE_STATUS_RUNNING_TO_HOLD % will_pause_at
    elif will_stop_at:
        return SUITE_STATUS_RUNNING_TO_STOP % will_stop_at
    else:
        return SUITE_STATUS_RUNNING


class SuiteStillInitialisingError(Exception):
    """Exception raised if a summary is requested before the first update.

    This can happen if client connects during start-up for large suites.

    """
    def __str__(self):
        return "Suite initializing..."


class StateSummaryServer(PyroServer):
    """Server-side suite state summary interface."""

    _INSTANCE = None
    TIME_FIELDS = ['submitted_time', 'started_time', 'finished_time']

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
        global_summary = {}
        family_summary = {}

        task_summary, task_states = self._get_tasks_info(tasks, tasks_rh)

        fam_states = {}
        all_states = []
        config = SuiteConfig.get_inst()
        ancestors_dict = config.get_first_parent_ancestors()

        # Compute state_counts (total, and per cycle).
        state_count_totals = {}
        state_count_cycles = {}

        for point_string, c_task_states in task_states:
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

        state_count_totals = {}
        for point_string, count in state_count_cycles.items():
            for state, state_count in count.items():
                state_count_totals.setdefault(state, 0)
                state_count_totals[state] += state_count

        all_states.sort()

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
        global_summary['states'] = all_states
        global_summary['namespace definition order'] = ns_defn_order
        global_summary['reloading'] = reloading
        global_summary['state totals'] = state_count_totals

        # Construct a suite status string for use by monitoring clients.
        global_summary['status_string'] = get_suite_status_string(
            paused, stopping, will_pause_at, will_stop_at)

        # TODO - delete this block post back-compat concerns (<= 6.9.1):
        #  Report separate status string components for older clients that
        # construct their own suite status strings.
        global_summary['paused'] = paused
        global_summary['stopping'] = stopping
        global_summary['will_pause_at'] = will_pause_at
        global_summary['will_stop_at'] = will_stop_at

        self._summary_update_time = time.time()

        # Replace the originals (atomic update, for access from other threads).
        self.task_summary = task_summary
        self.global_summary = global_summary
        self.family_summary = family_summary
        self.first_update_completed = True
        self.state_count_totals = state_count_totals
        self.state_count_cycles = state_count_cycles

    def _get_tasks_info(self, tasks, tasks_rh):
        """Retrieve task summary info and states."""

        task_summary = {}
        task_states = {}

        for task in tasks:
            ts = task.get_state_summary()
            task_summary[task.identity] = ts
            name, point_string = TaskID.split(task.identity)
            task_states.setdefault(point_string, {})
            task_states[point_string][name] = ts['state']

        for task in tasks_rh:
            ts = task.get_state_summary()
            ts['state'] = TASK_STATUS_RUNAHEAD
            task_summary[task.identity] = ts
            name, point_string = TaskID.split(task.identity)
            task_states.setdefault(point_string, {})
            task_states[point_string][name] = TASK_STATUS_RUNAHEAD

        return task_summary, task_states.items()

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

    def get_tasks_by_state(self):
        """Returns a dictionary containing lists of tasks by state in the form:
        {state: [(most_recent_time_string, task_name, point_string), ...]}."""
        check_access_priv(self, 'state-totals')

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

    def get_summary_update_time(self):
        """Return the last time the summaries were changed (Unix time)."""
        check_access_priv(self, 'state-totals')
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

    ordered_states = [TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_FAILED,
                      TASK_STATUS_EXPIRED, TASK_STATUS_SUBMIT_RETRYING,
                      TASK_STATUS_RETRYING, TASK_STATUS_RUNNING,
                      TASK_STATUS_SUBMITTED, TASK_STATUS_READY,
                      TASK_STATUS_QUEUED, TASK_STATUS_WAITING,
                      TASK_STATUS_HELD, TASK_STATUS_SUCCEEDED,
                      TASK_STATUS_RUNAHEAD]
    if is_stopped:
        ordered_states = [TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_FAILED,
                          TASK_STATUS_RUNNING, TASK_STATUS_SUBMITTED,
                          TASK_STATUS_EXPIRED, TASK_STATUS_READY,
                          TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RETRYING,
                          TASK_STATUS_SUCCEEDED, TASK_STATUS_QUEUED,
                          TASK_STATUS_WAITING, TASK_STATUS_HELD,
                          TASK_STATUS_RUNAHEAD]
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

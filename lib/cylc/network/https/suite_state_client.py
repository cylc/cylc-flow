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

from cylc.task_id import TaskID
from cylc.network import COMMS_STATE_OBJ_NAME
from cylc.network.https.base_client import BaseCommsClient
from cylc.network.https.util import unicode_encode
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


class StateSummaryClient(BaseCommsClient):
    """Client-side suite state summary interface."""

    METHOD = BaseCommsClient.METHOD_GET

    def get_suite_state_summary(self):
        return unicode_encode(
            self.call_server_func(COMMS_STATE_OBJ_NAME, "get_state_summary"))

    def get_suite_state_summary_update_time(self):
        return self.call_server_func(COMMS_STATE_OBJ_NAME,
                                     "get_summary_update_time")

    def get_tasks_by_state(self):
        return self.call_server_func(COMMS_STATE_OBJ_NAME,
                                     "get_tasks_by_state")


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

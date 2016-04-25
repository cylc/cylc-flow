#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
"""Utility for "cylc cat-state" and "cylc dump"."""

import time
from cylc.task_id import TaskID
from cylc.network.suite_state import SUITE_STATUS_STOPPED
from cylc.task_state import TASK_STATUS_READY


def get_stop_state_summary(lines):
    """Parse state dump content into summary maps."""
    global_summary = {}
    task_summary = {}
    if len(lines) == 0 or len(lines) < 3:
        return None
    for line in list(lines):
        if line.startswith('Remote command'):
            lines.remove(line)
    line0 = lines.pop(0)
    if line0.startswith('suite time') or \
            line0.startswith('simulation time'):
        # backward compatibility with pre-5.4.11 state dumps
        global_summary["last_updated"] = time.time()
    else:
        # (line0 is run mode)
        line1 = lines.pop(0)
        while not line1.startswith("time :"):
            line1 = lines.pop(0)
        try:
            time_string = line1.rstrip().split(' : ')[1]
            unix_time_string = time_string.rsplit('(', 1)[1].rstrip(")")
            global_summary["last_updated"] = int(unix_time_string)
        except (TypeError, ValueError, IndexError):
            # back compat pre cylc-6
            global_summary["last_updated"] = time.time()

    # Skip initial and final cycle points.
    lines[0:2] = []
    global_summary["status_string"] = SUITE_STATUS_STOPPED
    while lines:
        line = lines.pop(0)
        if line.startswith("class") or line.startswith("Begin task"):
            continue
        try:
            (task_id, info) = line.split(' : ')
            name, point_string = TaskID.split(task_id)
        except ValueError:
            continue
        task_summary.setdefault(task_id, {"name": name, "point": point_string,
                                          "label": point_string})
        # reconstruct state from a dumped state string
        items = dict([p.split("=") for p in info.split(', ')])
        state = items.get("status")
        if state == 'submitting':
            # backward compabitility for state dumps generated prior to #787
            state = TASK_STATUS_READY
        task_summary[task_id].update({"state": state})
        task_summary[task_id].update({"spawned": items.get("spawned")})
    global_summary["run_mode"] = "dead"
    return global_summary, task_summary


def dump_to_stdout(states, sort_by_cycle=False):
    """Print states in "cylc dump" format to STDOUT.

    states = {
        "task_id": {
            "name": name,
            "label": point,
            "state": state,
            "spawned": True|False},
        # ...
    }
    """
    lines = []
    for item in states.values():
        if item['spawned'] in [True, "True", "true"]:
            spawned = 'spawned'
        else:
            spawned = 'unspawned'
        if sort_by_cycle:
            values = [item['label'], item['name'], item['state'], spawned]
        else:
            values = [item['name'], item['label'], item['state'], spawned]
        lines.append(', '.join(values))

    lines.sort()
    for line in lines:
        print line

#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
import sys
import subprocess
import time
from cylc.task_id import TaskID


def get_stop_state(suite, owner=None, host=None):
    """Return the contents of the last 'state' file."""
    if not suite:
        # this occurs if we run gcylc with no suite argument
        return None
    command = "cylc cat-state"
    if host:
        command += " --host=" +host
    if owner:
        command += " --user=" + owner
    command += " " + suite
    try:
        p = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        stdout, stderr = p.communicate()
    except:
        return None
    if stdout:
        return stdout
    else:
        return None


def get_stop_state_summary(suite, owner=None, hostname=None, lines=None ):
    """Load the contents of the last 'state' file into summary maps."""
    global_summary = {}
    task_summary = {}
    family_summary = {}
    if not lines:
        state_file_text = get_stop_state(suite, owner, hostname)
        if state_file_text is None:
            return global_summary, task_summary, family_summary
        lines = state_file_text.splitlines()
    if len(lines) == 0 or len(lines) < 3:
        return None
    for line in list(lines):
        if line.startswith('Remote command'):
            lines.remove(line)
    line0 = lines.pop(0)
    if line0.startswith( 'suite time' ) or \
            line0.startswith( 'simulation time' ):
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
  
    start = lines.pop(0).rstrip().rsplit(None, 1)[-1]
    stop = lines.pop(0).rstrip().rsplit(None, 1)[-1]
    if start != "(none)":
        global_summary["start time"] = start
    if stop != "(none)":
        global_summary["will_stop_at"] = stop
    while lines:
        line = lines.pop(0)
        if line.startswith("class") or line.startswith("Begin task"):
            continue
        try:
            ( task_id, info ) = line.split(' : ')
            name, point_string = TaskID.split(task_id)
        except ValueError:
            continue
        except Exception as e:
            sys.stderr.write(str(e) + "\n")
            continue
        task_summary.setdefault(task_id, {"name": name, "point": point_string,
                                          "label": point_string})
        # reconstruct state from a dumped state string
        items = dict([p.split("=") for p in info.split(', ')])
        state = items.get("status")
        if state == 'submitting':
            # backward compabitility for state dumps generated prior to #787
            state = 'ready'
        task_summary[task_id].update({"state": state })
        task_summary[task_id].update({"spawned": items.get("spawned")})
    global_summary["run_mode"] = "dead"
    for key in ["paused", "stopping", "will_pause_at", "will_stop_at"]:
        global_summary.setdefault(key, "")
    return global_summary, task_summary, family_summary

def dump_to_stdout( states, sort_by_cycle=False ):
    lines = []
    #print 'TASK INFORMATION'
    task_ids = states.keys()
    #task_ids.sort()

    for id in task_ids:
        name  = states[ id ][ 'name' ]
        label = states[ id ][ 'label' ]
        state = states[ id ][ 'state' ]

        if states[ id ][ 'spawned' ]:
            spawned = 'spawned'
        else:
            spawned = 'unspawned'

        if sort_by_cycle:
            line = label + ', ' + name + ', '
        else:
            line = name + ', ' + label + ', '

        line += state + ', ' + spawned

        lines.append( line )

    lines.sort()
    for line in lines:
        print line

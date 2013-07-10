#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

import datetime, time
import subprocess
from cylc.TaskID import TaskID

def get_stop_state(suite, owner=None, host=None):
    """Return the contents of the last 'state' file."""
    if not suite:
        # this occurs if we run gcylc with no suite argument
        return None
    command = "cylc cat-state"
    if host:
        command += " --host=" +host
    if owner:
        command += " --owner=" + owner
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
    [ time_type, time_string ] = lines.pop(0).rstrip().split(' : ')
    time_string = time_string.rsplit(",")[0]

    # datetime.strptime() introduced in Python 2.5
    ##dt = datetime.datetime.strptime(time_string, "%Y:%m:%d:%H:%M:%S")
    # but is equivalent to this:
    dt = datetime.datetime( *(time.strptime(time_string, "%Y:%m:%d:%H:%M:%S")[0:6]))

    global_summary["last_updated"] = dt
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
            ( name, tag ) = task_id.split( TaskID.DELIM )
        except:
            continue
        task_summary.setdefault(task_id, {"name": name, "tag": tag,
                                          "label": tag})
        # reconstruct state from a dumped state string
        items = dict([p.split("=") for p in info.split(', ')])
        task_summary[task_id].update({"state": items.get("status")})
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

        if 'asyncid' in states[id]:
            line += ', ' + states[id]['asyncid']

        lines.append( line )

    lines.sort()
    for line in lines:
        print line


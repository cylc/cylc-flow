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

import Pyro.core
import logging
from TaskID import TaskID
import time


class state_summary( Pyro.core.ObjBase ):
    """supply suite state summary information to remote cylc clients."""

    def __init__( self, config, run_mode, start_time ):
        Pyro.core.ObjBase.__init__(self)
        self.task_summary = {}
        self.global_summary = {}
        self.task_name_list = []
        self.family_summary = {}
        # external monitors should access config via methods in this
        # class, in case config items are ever updated dynamically by
        # remote control
        self.config = config
        self.run_mode = run_mode
        self.start_time = start_time
        self._summary_update_time = None
 
    def update( self, tasks, clock, oldest, newest,
            paused, will_pause_at, stopping, will_stop_at, runahead ):

        task_name_list = []
        task_summary = {}
        global_summary = {}
        family_summary = {}
        task_states = {}

        for task in tasks:
            task_summary[ task.id ] = task.get_state_summary()
            name, ctime = task.id.split(TaskID.DELIM)
            task_states.setdefault(ctime, {})
            task_states[ctime][name] = task_summary[task.id]['state']
            if name not in task_name_list:
                task_name_list.append(name)

        fam_states = {}
        all_states = []
        for ctime, c_task_states in task_states.items():
            # For each cycle time, construct a family state tree
            # based on the first-parent single-inheritance tree

            c_fam_task_states = {}
            
            for key, parent_list in self.config.get_first_parent_ancestors().items():
                state = task_states.get(ctime, {}).get(key)
                if state is None:
                    continue
                all_states.append( state )
                for parent in parent_list:
                    if parent == key:
                        continue
                    c_fam_task_states.setdefault(parent, [])
                    c_fam_task_states[parent].append(state)
            
            for fam, child_states in c_fam_task_states.items():
                f_id = fam + TaskID.DELIM + ctime
                state = extract_group_state(child_states)
                if state is None:
                    continue
                family_summary[f_id] = {'name': fam,
                                        'label': ctime,
                                        'state': state}
        
        all_states.sort()

        global_summary[ 'start time' ] = self.start_time
        global_summary[ 'oldest cycle time' ] = oldest
        global_summary[ 'newest cycle time' ] = newest
        global_summary[ 'last_updated' ] = clock.get_datetime()
        global_summary[ 'run_mode' ] = self.run_mode
        global_summary[ 'clock_rate' ] = clock.get_rate()
        global_summary[ 'paused' ] = paused
        global_summary[ 'stopping' ] = stopping
        global_summary[ 'will_pause_at' ] = will_pause_at
        global_summary[ 'will_stop_at' ] = will_stop_at
        global_summary[ 'runahead limit' ] = runahead
        global_summary[ 'states' ] = all_states

        if (self._summary_update_time is None or
                sorted(task_name_list) != sorted(self.task_name_list) or
                not compare_dict_of_dict(task_summary, self.task_summary) or
                not _compare_global_summaries(global_summary,
                                              self.global_summary) or
                not compare_dict_of_dict(family_summary, self.family_summary)):
            # Store the time of the change.
            self._summary_update_time = time.time()
        # replace the originals
        self.task_name_list = task_name_list
        self.task_summary = task_summary
        self.global_summary = global_summary
        self.family_summary = family_summary
        task_states = {}

    def get_task_name_list( self ):
        """Return the list of active task ids."""
        self.task_name_list.sort()
        return self.task_name_list
            
    def get_state_summary( self ):
        """Return the global, task, and family summary data structures."""
        return [ self.global_summary, self.task_summary, self.family_summary ]

    def get_summary_update_time( self ):
        """Return the last time the summaries were changed (Unix time)."""
        return self._summary_update_time


def compare_dict_of_dict( one, two ):
    """Return True if one == two, else return False."""
    for key in one:
        if key not in two:
            return False
        for subkey in one[ key ]:
            if subkey not in two[ key ]:
                return False
            if one[key][subkey] != two[key][subkey]:
                return False

    for key in two:
        if key not in one:
            return False
        for subkey in two[ key ]:
            if subkey not in one[ key ]:
                return False
            if two[key][subkey] != one[key][subkey]:
                return False

    return True


def _compare_global_summaries( one, two ):
    """Compare global summaries - return True if one == two."""
    if set(one.keys()) ^ set(two.keys()):
        # Non-shared keys.
        return False
    for key, one_value in one.items():
        two_value = two[ key ]
        if one_value != two_value:
            return False
    return True        


def extract_group_state( child_states, is_stopped=False ):
    """Summarise child states as a group."""
    ordered_states = ['submit-failed', 'failed', 'submit-retrying', 'retrying', 'running',
            'submitted', 'submitting', 'queued', 'waiting', 'held',
            'runahead', 'succeeded']
    if is_stopped:
        ordered_states = ['submit-failed', 'failed', 'running', 'submitted',
            'submitting', 'submit-retrying', 'retrying', 'succeeded', 'queued', 'waiting',
            'runahead', 'held']
    for state in ordered_states:
        if state in child_states:
            return state
    return None


def get_id_summary( id_, task_state_summary, fam_state_summary, id_family_map ):
    """Return some state information about a task or family id."""
    prefix_text = ""
    sub_text = ""
    sub_states = {}
    stack = [( id_, 0 )]
    done_ids = []
    while stack:
        this_id, depth = stack.pop( 0 )
        if this_id in done_ids:  # family dive down will give duplicates
            continue
        done_ids.append( this_id )
        prefix = "\n" + " " * 4 * depth + this_id + " "
        if this_id in task_state_summary:
            state = task_state_summary[this_id]['state']
            sub_text += prefix + state
            sub_states.setdefault( state, 0 )
            sub_states[state] += 1
        elif this_id in fam_state_summary:
            name, ctime = this_id.split( TaskID.DELIM )
            sub_text += prefix + fam_state_summary[this_id]['state']
            for child in reversed( sorted( id_family_map[name] ) ):
                child_id = child + TaskID.DELIM + ctime
                stack.insert( 0, ( child_id, depth + 1 ) )
        if not prefix_text:
            prefix_text = sub_text.strip()
            sub_text = ""
    if len( sub_text.splitlines() ) > 10:
        state_items = sub_states.items()
        state_items.sort()
        state_items.sort( lambda x, y: cmp( y[1], x[1] ) )
        sub_text = ""
        for state, number in state_items:
            sub_text += "\n    {0} tasks {1}".format( number, state )
    text = prefix_text + sub_text
    if not text:
        return id_
    return text


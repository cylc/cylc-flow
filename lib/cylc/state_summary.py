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

import Pyro.core
import logging
import TaskID
from cylc.strftime import strftime
import time
from datetime import datetime
from wallclock import now


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

    def update( self, tasks, oldest, newest, newest_nonrunahead,
            paused, will_pause_at, stopping, will_stop_at, runahead ):

        task_name_list = []
        task_summary = {}
        global_summary = {}
        family_summary = {}
        task_states = {}

        for task in tasks:
            task_summary[ task.id ] = task.get_state_summary()
            name, ctime = TaskID.split( task.id )
            ctime = str(ctime)
            task_states.setdefault(ctime, {})
            task_states[ctime][name] = task_summary[task.id]['state']
            task_name_list.append(name)

        task_name_list = list(set(task_name_list))

        fam_states = {}
        all_states = []
        for ctime, c_task_states in task_states.items():
            # For each cycle time, construct a family state tree
            # based on the first-parent single-inheritance tree

            c_fam_task_states = {}
            c_task_states = task_states.get(ctime, {})

            for key, parent_list in self.config.get_first_parent_ancestors().items():
                state = c_task_states.get(key)
                if state is None:
                    continue
                all_states.append( state )
                for parent in parent_list:
                    if parent == key:
                        continue
                    c_fam_task_states.setdefault(parent, [])
                    c_fam_task_states[parent].append(state)

            for fam, child_states in c_fam_task_states.items():
                f_id = TaskID.get( fam, ctime )
                state = extract_group_state(child_states)
                if state is None:
                    continue
                try:
                    famcfg = self.config.cfg['runtime'][fam]
                except KeyError:
                    famcfg = {}
                description = famcfg.get('description')
                title = famcfg.get('title')
                family_summary[f_id] = {'name': fam,
                                        'description': description,
                                        'title': title,
                                        'label': ctime,
                                        'state': state}

        all_states.sort()

        global_summary[ 'start time' ] = self.str_or_None(self.start_time)
        global_summary[ 'oldest cycle time' ] = self.str_or_None(oldest)
        global_summary[ 'newest cycle time' ] = self.str_or_None(newest)
        global_summary[ 'newest non-runahead cycle time' ] = self.str_or_None(newest_nonrunahead)
        global_summary[ 'last_updated' ] = now()
        global_summary[ 'run_mode' ] = self.run_mode
        global_summary[ 'paused' ] = paused
        global_summary[ 'stopping' ] = stopping
        global_summary[ 'will_pause_at' ] = self.str_or_None(will_pause_at)
        global_summary[ 'will_stop_at' ] = self.str_or_None(will_stop_at)
        global_summary[ 'runahead limit' ] = self.str_or_None(runahead)
        global_summary[ 'states' ] = all_states

        self._summary_update_time = time.time()
        # replace the originals
        self.task_name_list = task_name_list
        self.task_summary = task_summary
        self.global_summary = global_summary
        self.family_summary = family_summary
        task_states = {}

    def str_or_None( self, s ):
        if s:
            return str(s)
        else:
            return None

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


def extract_group_state( child_states, is_stopped=False ):
    """Summarise child states as a group."""
    ordered_states = ['submit-failed', 'failed', 'submit-retrying', 'retrying', 'running',
            'submitted', 'ready', 'queued', 'waiting', 'held',
            'runahead', 'succeeded']
    if is_stopped:
        ordered_states = ['submit-failed', 'failed', 'running', 'submitted',
            'ready', 'submit-retrying', 'retrying', 'succeeded', 'queued', 'waiting',
            'runahead', 'held']
    for state in ordered_states:
        if state in child_states:
            return state
    return None


def get_id_summary( id_, task_state_summary, fam_state_summary, id_family_map ):
    """Return some state information about a task or family id."""
    prefix_text = ""
    meta_text = ""
    sub_text = ""
    sub_states = {}
    stack = [( id_, 0 )]
    done_ids = []
    for summary in [task_state_summary, fam_state_summary]:
        if id_ in summary:
            title = summary[id_].get('title')
            if title:
                meta_text += title.strip() + "\n"
            description = summary[id_].get('description')
            if description:
                meta_text += description.strip()
    if meta_text:
        meta_text = "\n" + meta_text.rstrip()
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
            name, ctime = TaskID.split( this_id )
            sub_text += prefix + fam_state_summary[this_id]['state']
            for child in reversed( sorted( id_family_map[name] ) ):
                child_id = TaskID.get( child, ctime )
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
    if sub_text and meta_text:
        sub_text = "\n" + sub_text
    text = prefix_text + meta_text + sub_text
    if not text:
        return id_
    return text


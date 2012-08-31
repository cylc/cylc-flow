#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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


class state_summary( Pyro.core.ObjBase ):
    """supply suite state summary information to remote cylc clients."""

    def __init__( self, config, run_mode, start_time, gcylc=False ):
        Pyro.core.ObjBase.__init__(self)
        self.gcylc = gcylc
        self.task_summary = {}
        self.global_summary = {}
        # external monitors should access config via methods in this
        # class, in case config items are ever updated dynamically by
        # remote control
        self.config = config
        self.run_mode = run_mode
        self.start_time = start_time
 
    def update( self, tasks, clock, oldest, newest,
            paused, will_pause_at, stopping, will_stop_at, blocked, 
            runahead ):
        self.task_name_list = []
        self.task_summary = {}
        self.global_summary = {}
        self.family_summary = {}
        task_states = {}

        for task in tasks:
            self.task_summary[ task.id ] = task.get_state_summary()
            name, ctime = task.id.split('%')
            task_states.setdefault(ctime, {})
            task_states[ctime][name] = self.task_summary[task.id]['state']
            if name not in self.task_name_list:
                self.task_name_list.append(name)

        fam_states = {}
        for ctime, c_task_states in task_states.items():
            # For each cycle time, construct a family state tree           
            c_fam_task_states = {}
            
            for key, parent_list in self.config.family_hierarchy.items():
                state = task_states.get(ctime, {}).get(key)
                if state is None:
                    continue
                for parent in parent_list:
                    if parent == key:
                        continue
                    c_fam_task_states.setdefault(parent, [])
                    c_fam_task_states[parent].append(state)
            
            for fam, child_states in c_fam_task_states.items():
                f_id = fam + "%" + ctime
                state = extract_group_state(child_states)
                if state is None:
                    continue
                self.family_summary[f_id] = {'name': fam,
                                             'label': ctime,
                                             'state': state}
        
        self.global_summary[ 'start time' ] = self.start_time
        self.global_summary[ 'oldest cycle time' ] = oldest
        self.global_summary[ 'newest cycle time' ] = newest
        self.global_summary[ 'last_updated' ] = clock.get_datetime()
        self.global_summary[ 'run_mode' ] = self.run_mode
        self.global_summary[ 'clock_rate' ] = clock.get_rate()
        self.global_summary[ 'paused' ] = paused
        self.global_summary[ 'stopping' ] = stopping
        self.global_summary[ 'will_pause_at' ] = will_pause_at
        self.global_summary[ 'will_stop_at' ] = will_stop_at
        self.global_summary[ 'started by gcylc' ] = self.gcylc
        self.global_summary[ 'blocked' ] = blocked
        self.global_summary[ 'runahead limit' ] = runahead

    def get_task_name_list( self ):
        return self.task_name_list
            
    def get_state_summary( self ):
        return [ self.global_summary, self.task_summary, self.family_summary ]


def extract_group_state( child_states ):
    """Summarise child states as a group."""
    ordered_states = ['failed', 'held', 'running', 'submitted',
                        'retry_delayed', 'queued', 'waiting', 'runahead',
                        'succeeded']
    for state in ordered_states:
        if state in child_states:
            return state
    return None

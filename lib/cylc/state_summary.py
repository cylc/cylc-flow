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

    def __init__( self, config, simulation_mode, start_time, gcylc=False ):
        Pyro.core.ObjBase.__init__(self)
        self.gcylc = gcylc
        self.task_summary = {}
        self.global_summary = {}
        # external monitors should access config via methods in this
        # class, in case config items are ever updated dynamically by
        # remote control
        self.config = config
        self.simulation_mode = simulation_mode
        self.start_time = start_time
 
    def update( self, tasks, clock, oldest, newest,
            paused, will_pause_at, stopping, will_stop_at, blocked ):
        self.task_summary = {}
        self.global_summary = {}
        self.family_summary = {}
        task_states = {}

        for task in tasks:
            self.task_summary[ task.id ] = task.get_state_summary()
            name, ctime = task.id.split( '%' )
            task_states.setdefault(ctime, {})
            task_states[ctime][name] = self.task_summary [ task.id ][ 'state' ]

        tree = self.config.family_tree
        fam_states = {}
        for ctime in task_states.keys():
            # For each time, construct a family state tree
            fam_states.setdefault(ctime, {})
            stack = tree.keys()
            c_fam_states = fam_states[ctime]
            c_task_states = task_states[ctime]
            while len(stack) > 0:
                node = stack.pop()
                if [node in c_task_states or
                    node in c_fam_states]:
                    continue
                can_get_state = True
                child_states = []
                for child in tree[node]:
                    if child in c_task_states:
                        child_states.append(c_task_states[child])
                    elif child in c_fam_states:
                        child_states.append(c_fam_states[child])
                    else:
                        stack.append(child)
                        can_get_state = False
                if child_states and can_get_state:
                    node_id = ctime + "%" + node
                    state = self.extract_group_state(child_states)
                    self.family_summary[node_id] = { 'name': node,
                                                     'label': ctime,
                                                     'state':  state }
                    c_fam_states[node] = state
                else:
                    stack.append(node)
                         
        self.global_summary[ 'start time' ] = self.start_time
        self.global_summary[ 'oldest cycle time' ] = oldest
        self.global_summary[ 'newest cycle time' ] = newest
        self.global_summary[ 'last_updated' ] = clock.get_datetime()
        self.global_summary[ 'simulation_mode' ] = self.simulation_mode
        self.global_summary[ 'simulation_clock_rate' ] = clock.get_rate()
        self.global_summary[ 'paused' ] = paused
        self.global_summary[ 'stopping' ] = stopping
        self.global_summary[ 'will_pause_at' ] = will_pause_at
        self.global_summary[ 'will_stop_at' ] = will_stop_at
        self.global_summary[ 'started by gcylc' ] = self.gcylc
        self.global_summary[ 'blocked' ] = blocked
            
        # update deprecated old-style summary (DELETE WHEN NO LONGER NEEDED)
        #self.get_summary()

    def get_state_summary( self ):
        return [ self.global_summary, self.task_summary, self.family_summary ]

    def extract_group_state( self, child_states ):
        """Summarise child states as a group."""
        if 'failed' in child_states:
            return 'failed'
        elif 'held' in child_states:
            return 'held'
        elif 'running' in child_states:
            return 'running'
        elif 'submitted' in child_states:
            return 'submitted'
        elif 'retry_delayed' in child_states:
            return 'retry_delayed'
        elif 'queued' in child_states:
            return 'queued'
        elif 'waiting' in child_states:
            return 'waiting'
        elif 'runahead' in child_states:
            return 'runahead'
        else:  # (all are succeeded)
            return 'succeeded'

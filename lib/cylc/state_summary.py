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
            name, ctime = task.id.split('%')
            task_states.setdefault(ctime, {})
            task_states[ctime][name] = self.task_summary[task.id]['state']

        tree = self.config.family_tree
        fam_states = {}
        for ctime, c_task_states in task_states.items():
            # For each time, construct a family state tree
            fam_states.setdefault(ctime, {})
            c_fam_states = fam_states[ctime]
            nodes_redone = []
            # A stack item contains a task/family name and their child dict.
            stack = []
            # Initialise the stack with the top names and children (just root)
            for key in tree:
                stack.append([key, tree[key]])
            # Begin depth-first tree search, building states as we go.
            while stack:
                node, subtree = stack.pop(0)
                if (node in c_task_states or node in c_fam_states):
                    # node and children don't need any state calculation.
                    continue
                is_first_attempt = node not in nodes_redone
                could_get_later = True
                child_states = []
                for child, grandchild_dict in subtree.items():
                    # Iterate through child task names and info.
                    if child in c_task_states:
                        child_states.append(c_task_states[child])
                    elif child in c_fam_states:
                        child_states.append(c_fam_states[child])
                    else:
                        # No state for this child
                        # Family and empty (base graph) nodes.
                        if (is_first_attempt and
                            isinstance(grandchild_dict, dict)):
                            # Child is a family, so calculate its state next.
                            # Dive down tree.
                            stack.insert(0, [child, subtree[child]])
                        else:
                            # Child is a task with no state (base graph).
                            child_states.append('NULL')
                            could_get_later = False
                if child_states:
                    # Calculate the node state.
                    node_id = node + "%" + ctime
                    state = self.extract_group_state(child_states)
                    self.family_summary[node_id] = {'name': node,
                                                    'label': ctime,
                                                    'state': state}
                    c_fam_states[node] = state
                elif could_get_later and is_first_attempt:
                    # Put this off until later (when the children are done).
                    stack.append([node, subtree])
                    nodes_redone.append(node)
        
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
        ordered_states = ['failed', 'held', 'running', 'submitted',
                          'retry_delayed', 'queued', 'waiting', 'runahead']
        for state in ordered_states:
            if state in child_states:
                return state
        # All child states must be 'succeeded'
        return 'succeeded'

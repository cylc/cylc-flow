#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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


import sys
from task import task
from cycle_time import ct
from copy import deepcopy

global state_changed
#state_changed = False
state_changed = True

# Cycling tasks: cycle time also required for a cold start. Init with: 
#  (1) cycle time
#  (2) state ('waiting', 'submitted', 'running', and 'succeeded' or 'failed')

# For a restart from previous state, however, some tasks may require
# additional state information to be stored in the state dump file.
# Take, for instance, a task foo that runs hourly and depends on the
# most recent available 12-hourly task bar, but is allowed to run ahead
# of bar to some extent, and changes its behavior according whether or
# not it was triggered by a "old" bar (i.e. one already used by the
# previous foo instance) or a "new" one. In this case, currently, we
# use a class variable in task type foo to record the cycle time of
# the most recent bar used by any foo instance. This is written to the
# the state dump file so that task foo does not have to automatically
# assume it was triggered by a "new" bar after a restart.

# To handle this difference in initial state information (between normal
# start and restart) task initialisation must use a default value of
# 'None' for the additional variables, and for a restart the task
# manager must instantiate each task with a flattened list of all the
# state values found in the state dump file.

class cycling( task ):
    
    intercycle = False
    # This is a statement that the task has only cotemporal dependants
    # and as such can be deleted as soon as there are no unsucceeded
    # tasks with cycle times equal to or older than its own cycle time
    # (prior to that we can't be sure that an older unsucceeded 
    # task won't give rise to a new task that does depend on the task
    # we're interested in). 

    # DERIVED CLASSES MUST OVERRIDE ready_to_spawn()

    def __init__( self, state ):
        # Call this AFTER derived class initialisation

        # Derived class init MUST define:
        #  * self.id after calling self.nearest_c_time()
        #  * prerequisites and outputs
        #  * self.env_vars 

        # Top level derived classes must define:
        #   <class>.instance_count = 0

        task.__init__( self, state )

    def nearest_c_time( self, rt ):
        # return the next time >= rt for which this task is valid
        rh = int( rt[8:10])
        incr = None
        first_vh = self.valid_hours[ 0 ]
        extra_vh = 24 + first_vh 
        foo = deepcopy( self.valid_hours )
        foo.append( extra_vh )

        for vh in foo:
            if rh <= vh:
                incr = vh - rh
                break
        nearest_rt = ct(rt)
        nearest_rt.increment( hours=incr )
        return nearest_rt.get()

    def ready_to_spawn( self ):
        # return True or False
        self.log( 'CRITICAL', 'ready_to_spawn(): OVERRIDE ME')
        sys.exit(1)

    def next_c_time( self, rt = None):
        # return the next cycle time, or the next cycle time
        # after rt, that is valid for this task.
        #--

        if not rt:
            # set proper default argument here (python does not allow
            # self.foo as a default argument)
            rt = self.c_time

        n_times = len( self.valid_hours )
        if n_times == 1:
            incr = 24
        else:
            i_now = self.valid_hours.index( int( rt[8:10]) )
            # list indices start at zero
            if i_now < n_times - 1 :
                incr = self.valid_hours[ i_now + 1 ] - self.valid_hours[ i_now ]
            else:
                incr = self.valid_hours[ 0 ] + 24 - self.valid_hours[ i_now ]

        foo = ct( rt )
        foo.increment( incr )
        return foo.get()

    def next_tag( self ):
        return self.next_c_time()

    def get_valid_hours( self ):
        return self.valid_hours

    def get_state_summary( self ):
        summary = task.get_state_summary( self )
        # derived classes can call this method and then 
        # add more information to the summary if necessary.
        summary[ 'cycle_time' ] = self.c_time   # (equiv to self.tag)
        return summary

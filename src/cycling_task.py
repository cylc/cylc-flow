#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import sys
from task import task
import task_state
import logging
import Pyro.core
import cycle_time
from copy import deepcopy

global state_changed
#state_changed = False
state_changed = True

# Cycling tasks: cycle time also required for a cold start. Init with: 
#  (1) cycle time
#  (2) state ('waiting', 'submitted', 'running', and 'finished' or 'failed')

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

# The abdication mechanism ASSUMES that the task manager creates the
# successor task as soon as the current task spawns.

class cycling_task( task ):
    
    # Default task deletion: quick_death = True
    # This amounts to a statement that the task has only cotemporal
    # downstream dependents (i.e. the only other tasks that depend on it
    # to satisfy their prerequisites have the same cycle time as it
    # does) and as such can be deleted at the earliest possible
    # opportunity - which is as soon as there are no non-finished
    # tasks with cycle times the same or older than its cycle
    # time (prior to that we can't be sure that an older non-finished 
    # task won't give rise (on abdicating) to a new task that does
    # depend on the task we're interested in). 

    # Tasks that are needed to satisfy the prerequisites of other tasks
    # in subsequent cycles, however, must set quick_death = False, in
    # which case they will be removed according to system cutoff time.
    quick_death = True

    # DERIVED CLASSES MUST OVERRIDE: ready_to_spawn()

    def __init__( self, state, no_reset ):
        # Call this AFTER derived class initialisation

        # Derived class init MUST define:
        #  * self.id after calling self.nearest_c_time()
        #  * prerequisites and outputs
        #  * self.env_vars 

        # Top level derived classes must define:
        #   <class>.instance_count = 0

        task.__init__( self, state, no_reset )

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
    
        nearest_rt = cycle_time.increment( rt, incr )
        return nearest_rt


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
            increment = 24
        else:
            i_now = self.valid_hours.index( int( rt[8:10]) )
            # list indices start at zero
            if i_now < n_times - 1 :
                increment = self.valid_hours[ i_now + 1 ] - self.valid_hours[ i_now ]
            else:
                increment = self.valid_hours[ 0 ] + 24 - self.valid_hours[ i_now ]

        return cycle_time.increment( rt, increment )

    def next_tag( self ):
        return self.next_c_time()

    def prev_c_time( self ):
        # return the previous cycle time valid for this task.
        #--

        rt = self.c_time

        n_times = len( self.valid_hours )
        if n_times == 1:
            increment = 24
        else:
            i_now = self.valid_hours.index( int( rt[8:10]) )
            # list indices start at zero
            if i_now > 0 :
                decrement = self.valid_hours[ i_now ] - self.valid_hours[ i_now - 1 ] 
            else:
                decrement = self.valid_hours[ i_now ] - self.valid_hours[ n_times - 1 ] + 24

        return cycle_time.decrement( rt, decrement )

    def get_valid_hours( self ):
        return self.valid_hours

    def get_state_summary( self ):
        summary = task.get_state_summary( self )
        # derived classes can call this method and then 
        # add more information to the summary if necessary.
        summary[ 'cycle_time' ] = self.c_time
        return summary

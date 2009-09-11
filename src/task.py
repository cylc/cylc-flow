#!/usr/bin/python

import sys
import task_state
import logging
import Pyro.core
import reference_time
from copy import deepcopy

global state_changed
#state_changed = False
state_changed = True

# NOTE ON TASK STATE INFORMATION---------------------------------------

# The only task attributes required for a CLEAN system start (i.e. from
# configured start time, rather than a previous dumped state) are:

#  (1) reference time
#  (2) state ('waiting', 'running', 'finished', or 'failed')

# The 'state' variable is initialised by the base class. The reference
# time is initialised by derived classes because it may be adjusted at
# start time according to the allowed values for each task type.  Both
# of these variables are written to the state dump file by the base
# class dump_state() method.

# For a restart from previous state, however, some tasks may require
# additional state information to be stored in the state dump file.
# Take, for instance, a task foo that runs hourly and depends on the
# most recent available 12-hourly task bar, but is allowed to run ahead
# of bar to some extent, and changes its behavior according whether or
# not it was triggered by a "old" bar (i.e. one already used by the
# previous foo instance) or a "new" one. In this case, currently, we
# use a class variable in task type foo to record the reference time of
# the most recent bar used by any foo instance. This is written to the
# the state dump file so that task foo does not have to automatically
# assume it was triggered by a "new" bar after a restart.

# To handle this difference in initial state information (between normal
# start and restart) task initialisation must use a default value of
# 'None' for the additional variables, and for a restart the task
# manager must instantiate each task with a flattened list of all the
# state values found in the state dump file.

# The abdication mechanism ASSUMES that the task manager creates the
# successor task as soon as the current task abdicates.

############ TASK BASE CLASS
class task_base( Pyro.core.ObjBase ):
    
    # Default task deletion: quick_death = True
    # This amounts to a statement that the task has only cotemporal
    # downstream dependents (i.e. the only other tasks that depend on it
    # to satisfy their prerequisites have the same reference time as it
    # does) and as such can be deleted at the earliest possible
    # opportunity - which is as soon as there are no non-finished
    # tasks with reference times the same or older than its reference
    # time (prior to that we can't be sure that an older non-finished 
    # task won't give rise (on abdicating) to a new task that does
    # depend on the task we're interested in). 

    # Tasks that are needed to satisfy the prerequisites of other tasks
    # in subsequent cycles, however, must set quick_death = False, in
    # which case they will be removed according to system cutoff time.
    quick_death = True

    @classmethod
    def describe( cls ):
        return cls.description 
        #for line in cls.description:
        #    print line


    def __init__( self, state = None ):
        # Call this AFTER derived class initialisation

        # Derived class init MUST define:
        #  * self.ref_time, using self.nearest_ref_time()
        #  * prerequisites and outputs
        #  * self.env_vars 

        self.state = task_state.task_state( state )

        # count instances of each top level object derived from task
        # top level derived classes must define:
        #   <class>.instance_count = 0

        # task types that need to DUMP and LOAD MORE STATE INFORMATION
        # should override __init__() but make the new state variables
        # default to None so that they aren't required for normal
        # startup: __init__( self, initial_state, foo = None )
        # On reload from state dump the task manager will call the 
        # task __init__() with a flattened list of whatever state values 
        # it finds in the state dump file.

        self.__class__.instance_count += 1

        Pyro.core.ObjBase.__init__(self)

        # set state_changed True if any task's state changes 
        # as a result of a remote method call
        global state_changed 
        state_changed = True

        self.latest_message = ""

        # check initial state 
        if self.state.is_finished():  
            self.log( 'WARNING', " starting in FINISHED state" )
            self.outputs.set_all_satisfied()
            self.prerequisites.set_all_satisfied()

    def get_identity( self ):
        # unique task id
        return self.name + '%' + self.ref_time

    def register_run_length( self, run_len_minutes ):
        # automatically define special 'started' and 'finished' outputs
        self.outputs.add( 0, self.get_identity() + ' started' )
        self.outputs.add( run_len_minutes, self.get_identity() + ' finished' )

    def log( self, priority, message ):
        # task-specific log file

        # is it better to "get" this each time as here, or to get a
        # 'self.logger' once in __init__?
        logger = logging.getLogger( "main." + self.name ) 

        # task logs are already specific to type so we only need to
        # preface each entry with reference time, not whole task id.
        message = '[' + self.ref_time + '] ' + message

        if priority == "WARNING":
            logger.warning( message )
        elif priority == "NORMAL":
            logger.info( message )
        elif priority == "DEBUG":
            logger.debug( message )
        elif priority == "CRITICAL":
            logger.critical( message )
        else:
            logger.warning( 'UNKNOWN PRIORITY: ' + priority )
            logger.warning( '-> ' + message )


    def prepare_for_death( self ):
        # The task manager MUST call this immediately before deleting a
        # task object. It decrements the instance count of top level
        # objects derived from task_base. It would be nice to use Python's
        # __del__() function for this, but that is only called when a
        # deleted object is about to be garbage collected (which is not
        # guaranteed to be right away).

        # NOTE: this was once used for constraining the number of
        # instances of each task type. However, it has not been used
        # since converting to a global contraint on the maximum number
        # of hours that any task can get ahead of the slowest one.

        self.__class__.instance_count -= 1

    def nearest_ref_time( self, rt ):
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
    
        nearest_rt = reference_time.increment( rt, incr )
        return nearest_rt


    def next_ref_time( self, rt = None):
        # return the next reference time, or the next reference time
        # after rt, that is valid for this task.
        #--

        if not rt:
            # set proper default argument here (python does not allow
            # self.foo as a default argument)
            rt = self.ref_time

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

        return reference_time.increment( rt, increment )


    def prev_ref_time( self ):
        # return the previous reference time valid for this task.
        #--

        rt = self.ref_time

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

        return reference_time.decrement( rt, decrement )

    def run_if_ready( self, launcher, clock ):
        # run if I am 'waiting' AND my prequisites are satisfied
        if self.state.is_waiting() and self.prerequisites.all_satisfied(): 
            self.run_external_task( launcher )

    def run_external_task( self, launcher ):
        self.log( 'DEBUG',  'launching external task' )
        dummy_out = False
        launcher.run( self.owner, self.name, self.ref_time, self.external_task, dummy_out, self.env_vars )
        self.state.set_status( 'running' )

    def is_complete( self ):  # not needed?
        if self.outputs.all_satisfied():
            return True
        else:
            return False

    def get_postrequisite_list( self ):
        return self.outputs.get_list()

    def get_timed_outputs( self ):
        return self.outputs.get_timed_requisites()

    def get_latest_message( self ):
        return self.latest_message

    def get_valid_hours( self ):
        return self.valid_hours

    def incoming( self, priority, message ):
        # receive all incoming pyro messages for this task 
        self.latest_message = message

        # set state_changed if this message satisfies any registered
        # output (indicates that the task manager needs to instigate a
        # new round of dependency renegotiations)
        global state_changed

        if not self.state.is_running():
            # my external task should not be running!
            self.log( 'WARNING', "UNEXPECTED MESSAGE (task should not be running)" )
            self.log( 'WARNING', '-> ' + message )

        # prefix task id to special messages.
        raw_message = message
        if message == 'started' or message == 'finished' or message == 'failed':
            message = self.get_identity() + ' ' + message
 
        if self.outputs.exists( message ):
            # registered output messages

            if not self.outputs.is_satisfied( message ):
                # message indicates completion of a registered output.
                state_changed = True
                self.log( priority,  message )
                self.outputs.set_satisfied( message )

                if message == self.get_identity() + ' finished':
                    # TASK HAS FINISHED
                    self.set_finished()
                    if not self.outputs.all_satisfied():
                        self.log( 'WARNING', 'finished before all outputs completed' )

            else:
                # this output has already been satisfied
                self.log( 'WARNING', "UNEXPECTED OUTPUT (already satisfied):" )
                self.log( 'WARNING', "-> " + message )

        elif raw_message == 'failed':
            # process task failure messages
            if priority != 'CRITICAL':
                self.log( 'WARNING', 'non-critical priority for task failure' )
            self.log( 'CRITICAL',  message )
            self.state.set_status( 'failed' )

        else:
            # log other (non-failed) unregistered messages with a '*' prefix
            message = '*' + message
            self.log( priority, message )

    def update( self, reqs ):
        for req in reqs.get_list():
            if req in self.prerequisites.get_list():
                # req is one of my prerequisites
                if reqs.is_satisfied(req):
                    self.prerequisites.set_satisfied( req )

    def get_real_time_delay( self ):
        # Return hours after reference to start running.
        # Used by dummy contact tasks in dummy mode.
        # Default, here, is to return None, which implies not a contact task
        # returning 0 => contact task starts running at reference time
        return None

    def dump_state( self, FILE ):
        # Write state information to the state dump file, reference time
        # first to allow users to sort the file easily in case they need
        # to edit it:
        #   reftime name state

        # This must be compatible with __init__() on reload

        FILE.write( self.ref_time     + ' ' + 
                    self.name         + ' ' + 
                    self.state.dump() + '\n' )


    def abdicate( self ):
        if self.state.has_abdicated():
            return False

        if self.ready_to_abdicate():
            self.state.set_abdicated()
            return True
        else:
            return False

    def has_abdicated( self ):
        # this exists in task class because the derived oneoff class 
        # needs to override it.
        return self.state.has_abdicated()

    def ready_to_abdicate( self ):
        # DERIVED CLASSES MUST OVERRIDE THIS METHOD
        print 'ERROR, illegal task base method called!'
        self.log( 'CRITICAL', 'illegal task base method called!' )
        sys.exit(1)

    def done( self ):
        # return True if task has finished and abdicated
        if self.state.is_finished() and self.state.has_abdicated():
            return True
        else:
            return False

    def get_state_summary( self ):
        # derived classes can call this method and then 
        # add more information to the summary if necessary.

        n_total = self.outputs.count()
        n_satisfied = self.outputs.count_satisfied()

        summary = {}
        summary[ 'name' ] = self.name
        summary[ 'short_name' ] = self.short_name
        summary[ 'state' ] = self.state.get_status()
        summary[ 'reference_time' ] = self.ref_time
        summary[ 'n_total_outputs' ] = n_total
        summary[ 'n_completed_outputs' ] = n_satisfied
        summary[ 'abdicated' ] = self.state.has_abdicated()
        summary[ 'latest_message' ] = self.latest_message
 
        return summary

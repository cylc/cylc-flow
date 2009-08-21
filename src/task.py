#!/usr/bin/python

import reference_time
from time import sleep

import os, sys, re
from copy import deepcopy
from time import strftime
import Pyro.core
import logging

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
# previous foo instance) or an "old" one. In this case, currently, we
# use a class variable in task type foo to record the reference time of
# the most recent bar used by any foo instance. This is written to the
# the state dump file so that task foo does not have to automatically
# assume it was triggered by a "new" bar after a restart.

# To handle this difference in initial state information (between normal
# start and restart) task initialisation must use a default value of
# 'None' for the additional variables, and for a restart the tast
# manager must instantiate each task with a flattened list of all the
# state values found in the state dump file.

# the abdication mechanism ASSUMES that the task manager creates the
# successor task as soon as the current task abdicates.

class task( Pyro.core.ObjBase ):
    
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

    def __init__( self, ref_time, abdicated, initial_state ):
        # Call this AFTER derived class initialisation
        # (which alters requisites based on initial state)

        # Derived classes MUST call nearest_ref_time() and define their 
        # prerequistes and outputs before calling this __init__.
        self.ref_time = ref_time

        # cutoff; see get_cutoff below
        self.my_cutoff_reftime = ref_time

        # Has this object abdicated yet (used for recreating abdicated
        # tasks when loading tasks from the state dump file).
        self.abdicated = abdicated

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

        # unique task identity
        self.identity = self.name + '%' + self.ref_time

        self.latest_message = ""

        if abdicated == 'True':
            # my successor has been created already
            self.abdicated = True
        else:
            # my successor has not been created yet
            self.abdicated = False 

        # initial states: 
        #  + waiting 
        #  + ready (prerequisites satisfied)
        #  + finished (outputs satisfied)
        if initial_state == "waiting": 
            self.state = "waiting"
        elif initial_state == "finished":  
            self.outputs.set_all_satisfied()
            self.log( 'WARNING', " starting in FINISHED state" )
            self.state = "finished"
        elif initial_state == "ready":
            # waiting, but ready to go
            self.state = "waiting"
            self.log( 'WARNING', " starting in READY state" )
            self.prerequisites.set_all_satisfied()
        else:
            self.log( 'CRITICAL',  "unknown initial task state: " + initial_state )
            sys.exit(1)

        #self.log( 'DEBUG', "initial state: " + initial_state )


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
        # objects derived from task. It would be nice to use Python's
        # __del__() function for this, but that is only called when a
        # deleted object is about to be garbage collected (which is not
        # guaranteed to be right away).

        # NOTE: this was once used for constraining the number of
        # instances of each task type. However, it has not been used
        # since converting to a global contraint on the maximum number
        # of hours that any task can get ahead of the slowest one.

        self.__class__.instance_count -= 1


    def get_cutoff( self, finished_task_dict ):
        # Return the reference time of the oldest tasks that the system
        # must retain in order to satisfy my prerequisites or, if my 
        # prerequisites have been satisfied but I have not abdicated
        # yet, those of my immediate successor. 

        # Tasks that depend on outputs from a previous reference time
        # can simply override self.my_cutoff_reftime with some fixed
        # offset, e.g. self.ref_time - 6 hours
        # MUST BE DONE AFTER BASE CLASS INIT or it won't override!

        # For horribly complicated variable scheduling behaviour
        # (e.g. EcoConnect's TopNet, we can override this method
        # and used finished_task_dict to find the most recent instance
        # of the task whose output we need.

        if not self.abdicated or not self.prerequisites.all_satisfied():

            # If I have not abdicated then my successor has not been
            # created yet so I must speak for it. Technically my
            # successor's cutoff  will be later than mine
            # (next_ref_time() in the simplest case) but just using my
            # cutoff is simpler, and safe because it is more
            # conservative.

            return self.my_cutoff_reftime

        else:
            # I've abdicated already (either running or finished)
            # Do not return a cutoff or else no spent tasks will ever
            # get deleted!
            return None


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


    def run_if_ready( self, launcher ):
        # run if I am 'waiting' AND my prequisites are satisfied
        if self.state == 'waiting' and self.prerequisites.all_satisfied(): 
            self.run_external_task( launcher )

    def run_external_task( self, launcher, extra_vars = [] ):
        self.log( 'DEBUG',  'launching extnernal task' )
        launcher.run( self.owner, self.name, self.ref_time, self.external_task, extra_vars )
        self.state = 'running'

    def get_state( self ):
        return self.name + ": " + self.state

    def display( self ):
        return self.name + "(" + self.ref_time + "): " + self.state

    def set_finished( self ):
        # could do this automatically off the "name finished for ref_time" message
        self.state = "finished"

    #def get_satisfaction( self, tasks ):
    #    for task in tasks:
    #        self.prerequisites.satisfy_me( task.outputs )

    def will_get_satisfaction( self, tasks ):
        temp_prereqs = deepcopy( self.prerequisites )
        for task in tasks:
            temp_prereqs.will_satisfy_me( task.outputs, task.identity )
    
        if not temp_prereqs.all_satisfied(): 
            return False
        else:
            return True

    def is_complete( self ):  # not needed?
        if self.outputs.all_satisfied():
            return True
        else:
            return False

    def is_running( self ): 
        if self.state == "running":
            return True
        else:
            return False

    def is_finished( self ): 
        if self.state == "finished":
            return True
        else:
            return False

    def is_not_finished( self ):
        if self.state != "finished":
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

        # prefix task id to special 'started' and 'finished' messages.
        # (other tasks may refer to "foo%finished" as a prerequisite).
        if message == 'started' or message == 'finished':
            message = self.identity + ' ' + message

        if self.state != "running":
            # my external task should not be running!
            self.log( 'WARNING', "UNEXPECTED MESSAGE (task should not be running)" )
            self.log( 'WARNING', '-> ' + message )

        if message == "failed":
            # process task failure messages
            if priority == "CRITICAL":
                self.log( 'CRITICAL',  message )
                self.state = "failed"
            else:
                self.log( 'WARNING', 'non-critical task failure message: ' )
                self.log( 'WARNING', "-> " + message )
  
        elif self.outputs.exists( message ):
            # process registered output messages
            if self.outputs.is_satisfied( message ):
                # this output has already been satisfied
                self.log( 'WARNING', "UNEXPECTED OUTPUT (already satisfied):" )
                self.log( 'WARNING', "-> " + message )
            else:
                # log the completed output and set it satisfied
                if priority == 'NORMAL':
                    self.log( 'NORMAL',  message )
                else:
                    self.log( 'WARNING', "UNEXPECTED PRIORITY FOR REGISTERED OUTPUT: " + priority )
                    self.log( 'WARNING', '-> ' + message )

                self.outputs.set_satisfied( message )
                state_changed = True

                # SET TASK FINISHED INDICATOR IF ALL OUTPUTS NOW SATISFIED
                if self.outputs.all_satisfied():
                    self.set_finished()
                    self.__class__.last_finished_ref_time = self.ref_time
        else:
            # log unregistered messages
            message = '*' + message
            if priority == "NORMAL":
                self.log( 'NORMAL',  message )
            elif priority == "WARNING":
                self.log( 'WARNING', message )
            elif priority == "CRITICAL":
                self.log( 'CRITICAL',  message )
            else:
                self.log( 'WARNING', "unknown priority " + priority )
                self.log( 'WARNING', '-> ' + message )


    def update( self, reqs ):
        for req in reqs.get_list():
            if req in self.prerequisites.get_list():
                # req is one of my prerequisites
                if reqs.is_satisfied(req):
                    self.prerequisites.set_satisfied( req )

    def get_state_string( self ):
        # Derived classes should override this function if they require
        # non-standard state information to be written to the state dump
        # file.

        # Currently only single string values allowed, FORMAT: 
        #    state:foo:bar:baz (etc.)

        return self.state


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
        #   reftime name abdicated state

        # Derived classes can override get_state_string() to add
        # information to the state dump file.
        
        # This must be compatible with __init__() on reload

        FILE.write( self.ref_time           + ' ' + 
                    self.name               + ' ' + 
                    str(self.abdicated)     + ' ' + 
                    self.get_state_string() + '\n' )


    def abdicate( self ):
        # the task manager should instantiate a new task when this one
        # abdicates (which only happens once per task). 
        if self.has_abdicated():
            return False

        if self.ready_to_abdicate():
            self.abdicated = True
            self.__class__.last_abdicated_ref_time = self.ref_time
            return True
        else:
            return False


    def set_abdicated( self ):
        self.abdicated = True


    def has_abdicated( self ):
        return self.abdicated


    def ready_to_abdicate( self ):

        if not self.outputs.previous_instance_dependence:
            # tasks with no PID (previous instance dependence) can
            # be abdicated at any time. 
            return True

        elif self.state == 'waiting':
            # never abdicate a waiting PID task 
            # (1) by definition, its successor has to wait on it running
            # (2) if the successor is created before then, it could get
            #     satisfied by later restart outputs of an earlier task
            #     (which we want to happen ONLY if the previous one
            #     fails).
            return False

        elif self.state == 'finished':
            # always abdicate a finished PID task
            return True

        else: 
            # running (and failed) PID tasks
            # (failed PID tasks are running before they fail, so will
            # already have abdicated or not, according to whether they
            # fail before or after the PID outputs).

            # ready only if all prev inst outputs are completed
            # (otherwise my successor's successor could trigger
            # off me, and so on).

            result = True
            for message in self.outputs.satisfied.keys():
                if re.search( 'restart files ready', message ) and not self.outputs.satisfied[ message ]:
                    result = False
                    break

            return result


    def done( self ):
        # return True if task has finished its active work
        # i.e. has (i) finished and (ii) abdicated
        if self.state == "finished" and self.abdicated:
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
        summary[ 'state' ] = self.state
        summary[ 'reference_time' ] = self.ref_time
        summary[ 'n_total_outputs' ] = n_total
        summary[ 'n_completed_outputs' ] = n_satisfied
        summary[ 'abdicated' ] = self.abdicated
        summary[ 'latest_message' ] = self.latest_message
 
        return summary

class contact_task( task ):
    # For tasks that wait on external events such as incoming external
    # data. These are the only tasks that can know if they are are
    # "caught up" or not, according to how their reference time relates
    # to current clock time.

    # The real contact task, once running (which occurs when all of its
    # prerequistes are satisfied), returns only when the external event
    # has occurred. This will be approximately after some known delay
    # relative to the task's reference time (e.g. data arrives 15 min
    # past the hour).  This delay interval needs to be defined for
    # accurate dummy mode simulation.  In catch up operation the
    # external task returns immediately because the external event has
    # already happened (i.e. the required data already exists).

    def __init__( self, ref_time, abdicated, initial_state, relative_state ):

        # catch up status is held as a class variable
        # (i.e. one for each *type* of task proxy object) 
        if relative_state == 'catching_up':
            self.__class__.catchup_mode = True
        else:
            # 'caught_up'
            self.__class__.catchup_mode = False

        # Catchup status needs to be written to the state dump file so
        # that we don't need to assume catching up at restart. 
        # Topnet, via its fuzzy prerequisites, can run out to
        # 48 hours ahead of nzlam when caught up, and only 12 hours
        # ahead when catching up.  Therefore if topnet is 18 hours, say,
        # ahead of nzlam when we stop the system, on restart the first
        # topnet to be created will have only a 12 hour fuzzy window,
        # which will cause it to wait for the next nzlam instead of
        # running immediately.

        # CHILD CLASS MUST DEFINE:
        #   self.real_time_delay
 
        task.__init__( self, ref_time, abdicated, initial_state )


    def get_real_time_delay( self ):

        return self.real_time_delay


    def get_state_string( self ):
        # for state dump file
        # see comment above on catchup_mode and restarts

        if self.__class__.catchup_mode:
            relative_state = 'catching_up'
        else:
            relative_state = 'caught_up'

        return self.state + ':' + relative_state


    def get_state_summary( self ):
        summary = task.get_state_summary( self )
        summary[ 'catching_up' ] = self.__class__.catchup_mode
        return summary


    def incoming( self, priority, message ):

        # pass on to the base class message handling function
        task.incoming( self, priority, message)
        
        # but intercept messages to do with catchup mode
        catchup_re  = re.compile( "^CATCHINGUP:" )
        uptodate_re = re.compile( "^CAUGHTUP:" )

        if catchup_re.match( message ):
            # message says we're catching up to real time
            if not self.__class__.catchup_mode:
                # We were caught up and have apparently slipped back a
                # bit. Do NOT revert to catching up mode because this
                # will suddenly reduce topnet's cutoff time
                # and may result in deletion of a finished nzlam task
                # that is still needed to satsify topnet prerequisites
                self.log( 'DEBUG',  'falling behind the pace a bit here' )
            else:
                # We were already catching up; no change.
                pass

        elif uptodate_re.match( message ):
            # message says we've caught up to real time
            if not self.__class__.catchup_mode:
                # were already caught up; no change
                pass
            else:
                # we have just caught up
                self.log( 'DEBUG',  'just caught up' )
                self.__class__.catchup_mode = False

class oneoff:

    def ready_to_abdicate( self ):
        # never abdicate (no successor)
        return False

    def done( self ):
        if state == 'finished':
            return True
        else:
            return False

class oneoff_task( task, oneoff ):
    def __init__( self, ref_time, abdicated, initial_state, relative_state):
        # initialise task with abdicated = True
        # NOTE THIS IS STRING 'True' not logical True!
        task.__init__( self, ref_time, 'True', initial_state, relative_state )

class oneoff_contact_task( contact_task, oneoff ):
    def __init__( self, ref_time, abdicated, initial_state, relative_state):
        # initialise contat with abdicated = True
        # NOTE THIS IS STRING 'True' not logical True!
        contact.__init__( self, ref_time, 'True', initial_state, relative_state )

#!/usr/bin/python

import reference_time
from requisites import requisites, timed_requisites, fuzzy_requisites
from time import sleep

import os, sys, re
from copy import deepcopy
from time import strftime
import Pyro.core
import logging

global state_changed
state_changed = False

#----------------------------------------------------------------------
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

    MAX_FINISHED = 5

    def prepare_for_death( self ):
        # The task manager MUST call this immediately before deleting a
        # task object. It decrements the instance count of top level
        # objects derived from task. It would be nice to use Python's
        # __del__() function for this, but that is only called when a
        # deleted object is about to be garbage collected (which is not
        # guaranteed to be right away).
        self.__class__.instance_count -= 1

    def __init__( self, initial_state ):
        # Call this AFTER derived class initialisation
        # (which alters requisites based on initial state)

        # Derived classes MUST call nearest_ref_time()
        # before defining their requisites.

        # count instances of each top level object derived from task
        # top level derived classes must define:
        #   <class>.instance_count = 0
        self.__class__.instance_count += 1

        Pyro.core.ObjBase.__init__(self)

        # set state_changed True if any task's state changes 
        # as a result of a remote method call
        global state_changed 
        state_changed = True

        # unique task identity
        self.identity = self.name + '%' + self.ref_time

        # my cutoff reference time
        self.my_cutoff = self.compute_cutoff( )

        # task-specific log file
        self.log = logging.getLogger( "main." + self.name ) 

        self.latest_message = ""

        self.abdicated = False # True => my successor has been created

        # initial states: 
        #  + waiting 
        #  + ready (prerequisites satisfied)
        #  + finished (postrequisites satisfied)
        if initial_state == "waiting": 
            self.state = "waiting"
        elif initial_state == "finished":  
            self.postrequisites.set_all_satisfied()
            self.log.warning( self.identity + " starting in FINISHED state" )
            self.state = "finished"
        elif initial_state == "ready":
            # waiting, but ready to go
            self.state = "waiting"
            self.log.warning( self.identity + " starting in READY state" )
            self.prerequisites.set_all_satisfied()
        else:
            self.log.critical( "unknown initial task state: " + initial_state )
            sys.exit(1)

        self.log.debug( "Creating new task in " + initial_state + " state, for " + self.ref_time )


    def compute_cutoff( self, rt = None ):
        # Return the reference time of the oldest tasks that the system
        # must retain in order to satisfy my prerequisites (if I am
        # waiting) or those of my immediate successor (if I am running). 
        # The non default argument allow me to compute the cutoff of 
        # my immediate successor (see below)

        # This base class method deals with the usual case of tasks with
        # only cotemporal (same reference time) upstream dependencies.

        # Override this method for tasks that depend on non-cotemporal
        # (earlier) tasks.

        if not rt:
            # can't use self.foo as a default argument
            rt = self.ref_time

        cutoff = rt
        return cutoff


    def get_cutoff( self ):
        if self.state == 'waiting':
            # return time of my upstream dependencies
            return self.my_cutoff

        elif self.state == 'running':
            # my prerequisites are already satisfied, but
            # my successor has not been created yet so 
            # I must speak for it.
            return self.compute_cutoff( self.next_ref_time( self.ref_time ) )

        elif self.state == 'failed':
            # manager should not delete me (so that the failed task
            # remains visible on the system monitor) but cutoff does
            # not concern me any more because I won't be abdicating.
            return '9999010100'

        elif self.state == 'finished':
            if not self.abdicated:
                # I've finished, but my successor has not been created
                # yet so I must speak for it.
                return self.compute_cutoff( self.next_ref_time( self.ref_time ) )
            else:
                # I've finished and my successor can
                # take care of its own cutoff time.
                return '9999010100'
        else:
            raise( 'get_cutoff called on illegal task state')


    def nearest_ref_time( self, rt ):
        # return the next time >= rt for which this task is valid
        rh = int( rt[8:10])
        incr = None
        first_vh = self.valid_hours[ 0 ]
        extra_vh = 24 + first_vh 
        foo = self.valid_hours
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
            # can't use self.foo as a default argument
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
        self.log.debug( 'launching task ' + self.name + ' for ' + self.ref_time )
        launcher.run( self.owner, self.name, self.ref_time, self.external_task, extra_vars )
        self.state = 'running'

    def get_state( self ):
        return self.name + ": " + self.state

    def display( self ):
        return self.name + "(" + self.ref_time + "): " + self.state

    def set_finished( self ):
        # could do this automatically off the "name finished for ref_time" message
        self.state = "finished"

    def get_satisfaction( self, tasks ):
        for task in tasks:
            self.prerequisites.satisfy_me( task.postrequisites )

    def will_get_satisfaction( self, tasks ):
        temp_prereqs = deepcopy( self.prerequisites )
        for task in tasks:
            temp_prereqs.will_satisfy_me( task.postrequisites )
    
        if not temp_prereqs.all_satisfied(): 
            return False
        else:
            return True

    def is_complete( self ):  # not needed?
        if self.postrequisites.all_satisfied():
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

    def get_postrequisites( self ):
        return self.postrequisites.get_requisites()

    def get_fullpostrequisites( self ):
        return self.postrequisites

    def get_postrequisite_list( self ):
        return self.postrequisites.get_list()

    def get_postrequisite_times( self ):
        return self.postrequisites.get_times()

    def get_latest_message( self ):
        return self.latest_message

    def get_valid_hours( self ):
        return self.valid_hours

    def incoming( self, priority, message ):
        # receive all incoming pyro messages for this task 

        global state_changed
        state_changed = True

        self.latest_message = message

        # if message does not end in 'for YYYYMMDDHH'
        # add my reference time for logging purposes
        # (and a semi-colon to identify these cases)
        if not re.search( 'for \d\d\d\d\d\d\d\d\d\d$', message ):
            log_message = message + '; for ' + self.ref_time
        else:
            log_message = message

        log_message = '(INCOMING) ' + log_message

        if self.state != "running":
            # message from a task that's not supposed to be running
            self.log.warning( "MESSAGE FROM NON-RUNNING TASK: " + log_message )

        if self.postrequisites.requisite_exists( message ):
            # an expected postrequisite from a running task
            if self.postrequisites.is_satisfied( message ):
                self.log.warning( "POSTREQUISITE ALREADY SATISFIED: " + log_message )

            self.log.info( log_message )
            self.postrequisites.set_satisfied( message )

        elif message == self.name + " failed":
            self.log.critical( log_message )
            self.state = "failed"

        else:
            # a non-postrequisite message, e.g. progress report
            log_message = '*' + log_message
            if priority == "NORMAL":
                self.log.info( log_message )
            elif priority == "WARNING":
                self.log.warning( log_message )
            elif priority == "CRITICAL":
                self.log.critical( log_message )
            else:
                self.log.warning( log_message )

        if self.postrequisites.all_satisfied():
            self.set_finished()

    def update( self, reqs ):
        for req in reqs.get_list():
            if req in self.prerequisites.get_list():
                # req is one of my prerequisites
                if reqs.is_satisfied(req):
                    self.prerequisites.set_satisfied( req )

    def dump_state( self, FILE ):

        # write a state string, 
        #   reftime:name:state
        # to the state dump file.  

        # Must be compatible with __init__ for reloading.

        # sub-classes can override this if they have other state
        # information that needs to be reloaded from the file.

        FILE.write( 
                self.ref_time + ":" + 
                self.name     + ":" + 
                self.state    + '\n' )

    def set_abdicated( self ):
        self.abdicated = True


    def has_abdicated( self ):
        if self.abdicated:
            return True
        else:
            return False


class sequential_task( task ) :
    # Embodies forecast model type tasks, which depend on their own
    # previous instance. This task therefore abdicates to the next
    # instance as soon as it is finished (which forces successive
    # instances to run sequentially).

    # There's no need to call task.__init__ explicitly unless I define
    # an __init__ function here.

    def abdicate( self ):

        if not self.abdicated and self.state == "finished": 
            if self.__class__.instance_count <= self.MAX_FINISHED:
                self.abdicated = True
                return True
            else:
                self.log.debug( "not abdicating " + self.identity + ": too many current instances")
                return False
        else:
            return False


class parallel_task( task ) :
    # Embodies non forecast model type tasks that do not depend on their
    # own previous instance.  This task therefore abdicates to the next
    # instance as soon as it starts running (so multiple instances can
    # run in parallel if other dependencies allow). 

    # There's no need to call task.__init__ explicitly unless I define
    # an __init__ function here.

    def abdicate( self ):
        if not self.abdicated:

            if self.prerequisites.count() == 0:
                # ARTIFICIALLY CONSTRAIN TOTALLY FREE TASKS TO 
                # SEQUENTIAL BEHAVIOUR
                if self.state == "finished" and \
                    self.__class__.instance_count <= self.MAX_FINISHED:
                    self.abdicated = True
                    return True
                else:
                    return False
                
            elif ( self.state == "running" or self.state == "finished" ) and \
                    self.__class__.instance_count <= self.MAX_FINISHED:
                self.abdicated = True
                return True
            else:
                return False
            
        else:
            return False


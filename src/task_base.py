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
class task_base( Pyro.core.ObjBase ):
    
    name = "task base"

    # By default, finished tasks can die as soon as their reference
    # time is older than that of the oldest non-finished task. Rare 
    # task types the system manager knows are needed to satisfy the 
    # prerequisites of tasks *in subsequent cycles*, however, must
    # set quick_death = False, in which case it will be removed by
    # cutoff time.

    # class defaults that can be overridden by instance variables:
    quick_death = True
    MAX_FINISHED = 5

    def __init__( self, ref_time, initial_state ):
        # Call this AFTER derived class initialisation
        #   (it alters requisites based on initial state)
        # Derived classes MUST call nearest_ref_time()
        #   before defining their requisites

        Pyro.core.ObjBase.__init__(self)

        # set state_changed True if any task's state changes 
        # as a result of a remote method call
        global state_changed 
        state_changed = True

        # unique task identity
        self.identity = self.name + '%' + self.ref_time


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


    def get_cutoff( self ):
        # Return the time beyond which all other tasks can be deleted as
        # far as this task is concerned.  For most tasks this is their
        # own reference time because they depend only on their
        # cotemporal peers (not even on previous instances of their own
        # task type, because of abdication):

        # OVERRIDE THIS METHOD for any tasks that depend on other
        # non-cotemporal (i.e. earlier) tasks.

        return self.ref_time

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


    def next_ref_time( self ):
        # return the next time that this task is valid at
        n_times = len( self.valid_hours )
        if n_times == 1:
            increment = 24
        else:
            i_now = self.valid_hours.index( int( self.ref_time[8:10]) )
            # list indices start at zero
            if i_now < n_times - 1 :
                increment = self.valid_hours[ i_now + 1 ] - self.valid_hours[ i_now ]
            else:
                increment = self.valid_hours[ 0 ] + 24 - self.valid_hours[ i_now ]

        return reference_time.increment( self.ref_time, increment )


    def run_if_ready( self, launcher ):
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

    def abdicate( self ):
        #print self.display()
        if self.state == "finished" and not self.abdicated:
            self.abdicated = True
            return True
        else:
            return False

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

        if self.state != "running":
            # message from a task that's not supposed to be running
            self.log.warning( "MESSAGE FROM NON-RUNNING TASK: " + message )

        if self.postrequisites.requisite_exists( message ):
            # an expected postrequisite from a running task
            if self.postrequisites.is_satisfied( message ):
                self.log.warning( "POSTREQUISITE ALREADY SATISFIED: " + message )

            self.log.info( message )
            self.postrequisites.set_satisfied( message )

        elif message == self.name + " failed":
            self.log.critical( message )
            self.state = "failed"

        else:
            # a non-postrequisite message, e.g. progress report
            message = '*' + message
            if priority == "NORMAL":
                self.log.info( message )
            elif priority == "WARNING":
                self.log.warning( message )
            elif priority == "CRITICAL":
                self.log.critical( message )
            else:
                self.log.warning( message )

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

        FILE.write( self.ref_time + ":" + self.name + ":" + self.state + '\n' )

#!/usr/bin/python

import reference_time
from requisites import requisites, timed_requisites, fuzzy_requisites
from time import sleep
import config
import job_submit

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

    def __init__( self, ref_time, initial_state ):
        # Call this AFTER derived class initialisation
        #   (it alters requisites based on initial state)
        # Derived classes MUST call nearest_ref_time()
        #   before defining their requisites

        Pyro.core.ObjBase.__init__(self)

        global state_changed 
        state_changed = True

        # unique task identity
        self.identity = self.name + '%' + self.ref_time

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

        if not config.dummy_mode and self.name in config.dummy_out:
            self.log.warning( "dummying out " + self.identity + " in real mode")

    def get_cutoff( self, all_tasks ):
        # Return the time beyond which all other tasks can be deleted as
        # far as this task is concerned.  For most tasks this is their
        # own reference time because they depend only on their
        # cotemporal peers (not even on previous instances of their own
        # task type, because of abdication):
        return self.ref_time

        # BUT OVERRIDE THIS METHOD for the few tasks (e.g. topnet) that
        # do depend on other non-cotemporal (earlier) tasks.

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


    def run_if_ready( self, tasks ):

        for task in tasks:
            # don't run if any previous instance of me is not finished
            if task.name == self.name:
                if task.state != "finished":
                    if int( task.ref_time ) < int( self.ref_time ):
                        self.log.debug( self.identity + " blocked by " + task.identity )
                        return


        if self.state == 'waiting' and self.prerequisites.all_satisfied():
            # prerequisites all satisified, so run me
            if config.dummy_mode or self.name in config.dummy_out:
                # we're in dummy mode
                self.run_external_dummy()
            else:
                self.run_external_task()

    def run_external_dummy( self ):
        self.log.info( "launching dummy for " + self.ref_time )
        os.system( './dummy_task.py ' + self.name + " " + self.ref_time + " &" )
        self.state = "running"

    def run_external_task( self, extra_vars = [] ):
        self.log.info( 'launching task for ' + self.ref_time )
        job_submit.run( self.user_prefix, self.name, self.ref_time, self.external_task, extra_vars )
        self.state = 'running'

    def get_state( self ):
        return self.name + ": " + self.state

    def display( self ):
        return self.name + "(" + self.ref_time + ")"

    def set_finished( self ):
        # could do this automatically off the "name finished for ref_time" message
        self.state = "finished"

    def abdicate( self ):
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

    def get_postrequisites( self ):
        return self.postrequisites.get_requisites()

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

        # print "HELLO FROM INCOMING: " + message

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

#----------------------------------------------------------------------
class simple_task( task_base ):
    # for tasks with minimal postrequisites: started, finished

    name = "simple task base"

    def __init__( self, ref_time, initial_state, est_run_time = 1 ):
        # est_run_time in minutes

        self.postrequisites = timed_requisites( self.name, [ 
            [0, self.name + " started for " + ref_time],
            [est_run_time, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class free_task( task_base ):
    # for tasks with no-prerequisites, e.g. downloader and nztide,
    # that would otherwise run ahead indefinitely: delay if we get
    # "too far ahead" based on number of existing finished tasks.

    name = "free task base"

    def __init__( self, ref_time, initial_state ):
        self.MAX_FINISHED = 2
        task_base.__init__( self, ref_time, initial_state )

    def run_if_ready( self, tasks ):
        # don't run if too many previous finished instances exist
        delay = False

        old_and_finished = []
        if self.state == "waiting":
            for task in tasks:
               if task.name == self.name and task.state == "finished":
                   old_and_finished.append( task.ref_time )
                            
            if len( old_and_finished ) >= self.MAX_FINISHED:
                delay = True

        if delay:
            # the following gets logged every time the function is called
            # self.log.debug( self.identity + " ready and waiting (too far ahead)" )
            pass

        else:
            task_base.run_if_ready( self, tasks )



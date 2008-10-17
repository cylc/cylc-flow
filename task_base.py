#!/usr/bin/python

# task base classes

import reference_time
from requisites import requisites, timed_requisites, fuzzy_requisites
from time import sleep

import os
import re
import sys
from copy import deepcopy
from time import strftime
import Pyro.core

import logging
import logging.handlers

from config import dummy_mode

import qsub

#----------------------------------------------------------------------
class task_base( Pyro.core.ObjBase ):
    "task base class"
    
    name = "task base class"

    def __init__( self, ref_time, initial_state ):
        # Call this AFTER derived class initialisation
        #   (it alters requisites based on initial state)
        # Derived classes MUST call nearest_ref_time()
        #   before defining their requisites

        Pyro.core.ObjBase.__init__(self)

        task_base.processing_required = True

        # unique task identity
        self.identity = self.name + '%' + self.ref_time

        self.log = logging.getLogger( "main." + self.name ) 

        self.latest_message = ""
        self.abdicated = False # True => my successor has been created

        # initial states: waiting, ready, running, finished
        if not initial_state:
            self.state = "waiting"
            pass
        elif initial_state == "waiting": 
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

    def oldest_to_keep( self, all_tasks ):
        # Most tasks depend only on their cotemporal peers
        # (not even their own previous instances because of abdication)
        # Therefore we can remove any batch of tasks older than the
        # oldest running task.

        if self.state != 'finished':
            return self.ref_time
        else:
            return None

        # BUT override this method for tasks with special dependency
        # requirements (e.g. topnet!)


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
            if dummy_mode:
                # we're in dummy mode
                self.run_external_dummy()
            else:
                self.run_external_task()

    def run_external_dummy( self ):
        self.log.critical( 'YOU MUST OVERRIDE THIS METHOD' )
        sys.exit(1)

    def run_external_task( self ):
        # RUN THE EXTERNAL TASK 
        # note that you can mix real and dummy tasks by temporarily
        # overriding this method to call run_external_dummy(), 
        self.log.info( 'launching external task for ' + self.ref_time )

        qsub.run( self.user_prefix, self.name, self.ref_time, self.external_task )
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

        task_base.processing_required = True

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
class free_task_base( task_base ):
    # for tasks with no-prerequisites, e.g. downloader and nztide,
    # that would otherwise run ahead indefinitely: delay if we get
    # "too far ahead" based on number of existing finished tasks.

    def __init__( self, ref_time, initial_state = "waiting" ):

        self.MAX_FINISHED = 4
        task_base.__init__( self, ref_time, initial_state )

        # logging is set up by task_base
        # self.log.info( self.identity + " max runahead: " + str( self.MAX_FINISHED ) + " tasks" )


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


#----------------------------------------------------------------------
class topnet_base ( task_base ):
    # topnet's special behaviour is encoded in the base class file
    # so that we don't have to put it in every task definition module
    # that includes topnet.

    def oldest_to_keep( self, all_tasks ):

        if self.state == 'finished':
            return None

        finished_nzlam_post_6_18_exist = False
        finished_nzlam_post_6_18 = []

        for task in all_tasks:
            # find any finished 6 or 18Z nzlam_post tasks
            if task.name == "nzlam_post" and task.state == "finished":
                hour = task.ref_time[8:10]
                if hour == "06" or hour == "18":
                    finished_nzlam_post_6_18_exist = True
                    finished_nzlam_post_6_18.append( task.ref_time )

        result = None
        if finished_nzlam_post_6_18_exist: 
            finished_nzlam_post_6_18.sort( key = int, reverse = True )
            for nzp_time in finished_nzlam_post_6_18:
                if int( nzp_time ) < int( self.ref_time ):
                    self.log.debug( "most recent finished 6 or 18Z nzlam_post older than me: " + nzp_time )
                    result = nzp_time
                    break

        return result




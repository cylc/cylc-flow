#!/usr/bin/python

"""
Class to parse an EcoConnect controller config file and handle task
creation according to the resulting configuration parameters (lists of
task names for particular transitional reference times).
"""

import reference_time
from tasks import *
from shared import pyro_daemon, state
from class_from_module import class_from_module
from task_config import task_config

from copy import deepcopy

import re
import sys
import Pyro.core

class task_manager ( Pyro.core.ObjBase ):
    def __init__( self, ref_time, filename = None ):

        print
        print "Initialising Task Manager"

        Pyro.core.ObjBase.__init__(self)
    
        self.initial_ref_time = ref_time

        self.config = task_config( filename )

        self.task_list = []

    def parse_config_file( self, filename ):
        self.config.parse_file( filename )

    def create_initial_tasks( self ):
        task_list = self.config.get_config( self.initial_ref_time )

        if len( task_list ) == 0:
           print "ERROR no tasks configured for " + self.initial_ref_time
           sys.exit( 1 )

        hour = self.initial_ref_time[8:10]
        for task_name in task_list:
           initial_state = None
           if re.compile( "^.*:").match( task_name ):
                [task_name, initial_state] = task_name.split(':')
                print "  + Creating " + task_name + " in " + initial_state + " state"

           task = class_from_module( "tasks", task_name )( self.initial_ref_time, initial_state )

           if hour not in task.get_valid_hours():
               print "  + " + task.name + " not valid for " + hour 
           else:
               self.task_list.append( task )
               # connect new task to the pyro daemon

               # if using an external pyro nameserver, unregister
               # objects from previous runs first:
               #try:
               #    pyro_daemon.disconnect( task )
               #except NamingError:
               #    pass

               uri = pyro_daemon.connect( task, task.identity() )

        print "Initial Task List:"
        for task in self.task_list:
            print " + " + task.identity()

    def check_for_dead_soldiers( self ):
        # check that all existing tasks can have their prerequisites
        # satisfied by other existing tasks
        dead_soldiers = []
        for task in self.task_list:
            if not task.will_get_satisfaction( self.task_list ):
                dead_soldiers.append( task )

        print
        if len( dead_soldiers ) == 0:
            print "Verified task list is self-consistent."
        else:
            print "ERROR: THIS TASK LIST IS NOT SELF-CONSISTENT, i.e. one"
            print "or more tasks have pre-requisites that are not matched"
            print "by others post-requisites, THEREFORE THEY WILL NOT RUN"
            for soldier in dead_soldiers:
                print " + ", soldier.identity()

            print
            sys.exit(1)

        print


    def run( self ):

        # Process once to start any tasks that have no prerequisites
        # We need at least one of these to start the system rolling 
        # (i.e. the downloader).  Thereafter things only happen only
        # when a running task gets a message via pyro). 
        self.create_initial_tasks()
        self.process_tasks()

        # process tasks again each time a request is handled
        pyro_daemon.requestLoop( self.process_tasks )

        # NOTE: this seems the easiest way to handle incoming pyro calls
        # AND run our task processing at the same time, but I might be 
        # using requestLoop's "condition" argument in an unorthodox way.
        # See pyro docs, as there are other ways to do this, if necessary.
        # E.g. use "handleRequests()" instead of "requestLoop", with a 
        # timeout that drops into our task processing loop.


    def process_tasks( self ):
        # this function gets called every time a pyro event comes in

        finished = {}

        if len( self.task_list ) == 0:
            print "ALL TASKS DONE"
            sys.exit(0)

        # lists to determine what's finished for each ref time
        all_finished = []

        # task interaction to satisfy prerequisites
        for task in self.task_list:
            task.get_satisfaction( self.task_list ) # INTERACTION
            task.run_if_satisfied()                 # RUN IF READY

            # create a new task foo(T+1) if foo(T) just finished
            if task.abdicate():
                task_name = task.name
                next_rt = reference_time.increment( task.ref_time, task.ref_time_increment )
                print "  + Creating " + task_name + " for " + next_rt
                # TO DO: for initial state, consult task_config
                statex = None
                new_task = class_from_module( "tasks", task_name )( next_rt, statex )
         
                new_hour = task.ref_time[8:10]
                if new_hour not in new_task.get_valid_hours():
                    print "  + " + new_task.name + " not valid for " + new_hour
                else:
                    self.task_list.append( new_task )
                    # connect new task to the pyro daemon

                    # if using an external pyro nameserver, unregister
                    # objects from previous runs first:
                    #try:
                    #    pyro_daemon.disconnect( new_task )
                    #except NamingError:
                    #    pass

                    uri = pyro_daemon.connect( new_task, new_task.identity() )

            # if there is a running downloader, delete any batch(T) of
            # tasks that are (a) all finished, and (b) older than the
            # downloader.

            if task.ref_time not in finished.keys():
                finished[ task.ref_time ] = [ task.is_finished() ]
            else:
                finished[ task.ref_time ].append( task.is_finished() )

            if task.name == "downloader" and task.is_running():
                downloader_time = task.ref_time

        # delete all tasks for a given ref time if they've all finished 
        remove = []
        for rt in finished.keys():
            if int( rt ) < int( downloader_time ):
                if False not in finished[rt]:
                    for task in self.task_list:
                        if task.ref_time == rt:
                            remove.append( task )

        if len( remove ) > 0:
            print
            print "removing spent tasks"
            for task in remove:
                print " + " + task.identity()
                self.task_list.remove( task )
                pyro_daemon.disconnect( task )

        del remove
   
        #    next_task_list = self.config.get_config( next_rt )

        state.update( self.task_list )

        return 1  # return 1 to keep the pyro requestLoop going


    def any_kupe_tasks( self, task_name_list ):
        # do any of the supplied tasks run on kupe?
        # (used in determining task overlap)

        for task_name in task_name_list:
           if re.compile( "^.*:").match( task_name ):
                [task_name, initial_state] = task_name.split(':')

           if class_from_module( "tasks", task_name ).runs_on_kupe:
               return True
 
        return False

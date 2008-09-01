#!/usr/bin/python

"""
Class to parse an EcoConnect controller config file and handle task
creation according to the resulting configuration parameters (lists of
task names for particular transitional reference times).
"""

from reference_time import reference_time
from dummy_tasks import *
from shared import pyro_daemon, state
from class_from_module import class_from_module
from task_config import task_config

from copy import deepcopy

import re
import sys
import Pyro.core

class task_manager ( Pyro.core.ObjBase ):
    def __init__( self, reftime, filename = None ):

        print
        print "Initialising Task Manager"

        Pyro.core.ObjBase.__init__(self)
    
        self.cycle_time = reference_time( reftime )

        self.config = task_config( filename )

        self.task_list = []


    def create_tasks( self ):

        print
        print "** NEW REFERENCE TIME " + self.cycle_time.to_str() + " **"

        #print "Initial Task Config for this cycle:"

        # get configured task list fo this cycle
        task_list = self.config.get_config( self.cycle_time.to_str() )

        if task_list[0] == 'stop':
           print "STOP requested; NOT creating new tasks"
           return

        hour = self.cycle_time.get_hour()
        for task_name in task_list:
           initial_state = None
           if re.compile( "^.*:").match( task_name ):
                [task_name, initial_state] = task_name.split(':')
                print "  + Creating " + task_name + " in " + initial_state + " state"

           task = class_from_module( "dummy_tasks", task_name )( self.cycle_time, initial_state )
           # TO DO: handle errors

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

        print "New Task List:"
        for task in self.task_list:
            print " + " + task.identity()

        # check that all tasks can have their prerequisites satisfied
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
        # We need at least one of this to start the system rolling 
        # (i.e. the downloader).  Thereafter things only happen only
        # when a running task gets a message via pyro). 
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

        # if no tasks present, then we've incremented reference time and
        # deleted the old tasks (see below)
        if len( self.task_list ) == 0:
            self.create_tasks()

        if len( self.task_list ) == 0:
            print "ALL TASKS DONE"
            sys.exit(0)

        # task interaction to satisfy prerequisites
        create_new = False
        for task in self.task_list:
            task.get_satisfaction( self.task_list )
            task.run_if_satisfied()
            if task.ref_time.to_str() not in finished.keys():
                finished[ task.ref_time.to_str() ] = [ task.is_finished() ]
            else:
                finished[ task.ref_time.to_str() ].append( task.is_finished() )

            if task.identity() == "B_" + self.cycle_time.to_str():
                if task.state == "finished":
                    print
                    print "SPECIAL FINISHED " + task.identity()
                    create_new = True

        if create_new:
            self.cycle_time.increment()
            self.create_tasks()

        state.update( self.task_list )

        # delete all tasks for a given ref time if they've all finished 
        remove = []
        for rt in finished.keys():
            if False not in finished[rt]:
                for task in self.task_list:
                    if task.ref_time.to_str() == rt:
                        remove.append( task )

        if len( remove ) > 0:
            print
            print "removing spent tasks"
            for task in remove:
                print " + " + task.identity()
                self.task_list.remove( task )
                pyro_daemon.disconnect( task )

        del remove

        return 1  # return 1 to keep the pyro requestLoop going

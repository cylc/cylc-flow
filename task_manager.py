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

from copy import deepcopy

import re
import sys
import Pyro.core

class task_manager ( Pyro.core.ObjBase ):
    def __init__( self, reftime, filename = None ):

        print
        print "Initialising Task Manager"

        Pyro.core.ObjBase.__init__(self)
    
        # newest cycle time
        self.cycle_time = reference_time( reftime )

        self.task_list = []
        self.ordered_ref_times = []

        if filename is not None:
            self.parse_config_file( filename )

    def parse_config_file( self, filename ):

        print
        print "Parsing Task Config File ..."

        self.ordered_ref_times = []

        config_task_lists = {}

        cfile = open( filename, 'r' )
        for line in cfile:

            # skip full line comments
            if re.compile( "^#" ).match( line ):
                continue

            # skip blank lines
            if re.compile( "^\s*$" ).match( line ):
                continue

            print " + ", line,

            # line format: "YYYYMMDDHH task1 task2 task3:finished [etc.]"
            tokens = line.split()
            ref_time = reference_time( tokens[0] )
            the_rest = tokens[1:]

            # check tasks are known
            for taskx in the_rest:
                task = taskx
                if re.compile( "^.*:").match( taskx ):
                    task = taskx.split(':')[0]

                if not task in task_manager.all_tasks:
                    if task != "stop" and task != "all":
                        print "ERROR: unknown task ", task
                        sys.exit(1)

            # add task list to the dict
            config_task_lists[ ref_time ] = the_rest

        cfile.close()

        # replace configured task dict
        self.config_task_lists = deepcopy( config_task_lists )

        # get ordered list of keys for the dict
        tmp = {}
        for rt in self.config_task_lists.keys():
            i_rt = rt.to_int() 
            tmp[ i_rt ] = rt

        o_i_rt = sorted( tmp.keys(), reverse = True )
        for rt in o_i_rt:
            self.ordered_ref_times.append( tmp[ rt ] )


    def create_tasks( self ):

        in_utero = ['all']

        if len( self.ordered_ref_times ) > 0:
            if self.cycle_time.is_lessthan( self.ordered_ref_times[-1] ):
                print
                print "WARNING: current reference time (" + self.cycle_time.to_str() + ") is EARLIER than"
                print "         first configured reference time (" + self.ordered_ref_times[-1].to_str() + "). I will"
                print "         instantiate ALL tasks for this reference time."
                print
                in_utero = task_manager.all_tasks

        for rt in self.ordered_ref_times:
            if self.cycle_time.is_greaterthan_or_equalto( rt ):
               in_utero = self.config_task_lists[ rt ]
               break
       
        if in_utero[0] == 'all':
            in_utero = task_manager.all_tasks

        print
        print "** NEW REFERENCE TIME " + self.cycle_time.to_str() + " **"
        print "Initial Task Config for this cycle:"
        print in_utero

        if in_utero[0] == 'stop':
            print "STOP requested; NOT creating new tasks"
            return

        hour = self.cycle_time.get_hour()
        #self.task_list = []
        for task_name in in_utero:
            initial_state = None
            if re.compile( "^.*:").match( task_name ):
                [task_name, initial_state] = task_name.split(':')
                print "  + Creating " + task_name + " in " + initial_state + " state"

            task = class_from_module( "dummy_tasks", task_name )( self.cycle_time, initial_state )
            # TO DO: handle errors

            if hour not in task.get_valid_hours():
                print "  + Removing " + task.name + " (not valid for " + hour + ")"
            else:
                self.task_list.append( task )
                # connect new task to the pyro daemon
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

        return 1  # return 1 to keep the pyro requestLoop going

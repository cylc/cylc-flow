#!/usr/bin/python

"""
Class to parse an EcoConnect controller config file and handle task
creation according to the resulting configuration parameters (lists of
task names for particular transitional reference times).
"""

from reference_time import reference_time
from dummy_tasks import *
from shared import pyro_daemon, state

import re
import sys

class task_manager:

    all_tasks = [ 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H' ]

    def __init__( self, reftime, filename = None ):

        print
        print "Initialising Task Manager"
    
        self.ordered_ref_times = []
        self.config_task_lists = {}
        self.task_list = []

        self.cycle_time = reference_time( reftime )

        # return now if no config file supplied
        if filename is None:
            self.config_supplied = False
            return

        self.config_supplied = True

        print
        print "Parsing Task Config File ..."

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

            # add to task_list dict
            self.config_task_lists[ ref_time ] = the_rest

        cfile.close()

        # get ordered list of keys for the dict
        tmp = {}
        for rt in self.config_task_lists.keys():
            i_rt = rt.to_int() 
            tmp[ i_rt ] = rt

        o_i_rt = sorted( tmp.keys(), reverse = True )
        for rt in o_i_rt:
            self.ordered_ref_times.append( tmp[ rt ] )


    def create_tasks( self ):

        if not self.config_supplied:
            in_utero = task_manager.all_tasks

        else:

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
            print
            print "STOP requested for", self.cycle_time.to_str()
            sys.exit(0)

        self.task_list = []
        for task_name in in_utero:
            initial_state = None
            if re.compile( "^.*:").match( task_name ):
                [task_name, initial_state] = task_name.split(':')
                print "  + Creating " + task_name + " in " + initial_state + " state"

            # TO DO: can I automate this based on list of valid tasks?
            if task_name == 'A':
                self.task_list.append( A( self.cycle_time, initial_state )) 
            elif task_name == 'B':
                self.task_list.append( B( self.cycle_time, initial_state ))
            elif task_name == 'C':
                self.task_list.append( C( self.cycle_time, initial_state ))
            elif task_name == 'D':
                self.task_list.append( D( self.cycle_time, initial_state )) 
            elif task_name == 'E':
                self.task_list.append( E( self.cycle_time, initial_state )) 
            elif task_name == 'F':
                self.task_list.append( F( self.cycle_time, initial_state ))
            elif task_name == 'G':
                self.task_list.append( G( self.cycle_time, initial_state ))
            elif task_name == 'H':
                self.task_list.append( H( self.cycle_time, initial_state ))
            else:
                print "ERROR: unknown task name", task_name
                sys.exit(1)
                # TO DO: handle errors

        hour = self.cycle_time.get_hour()
        for task in self.task_list:
           if hour not in task.get_valid_hours():
               print "  + Removing " + task.name + " (not valid for " + hour + ")"
               self.task_list.remove( task )

        print "Final Task List:"
        for task in self.task_list:
            print " + " + task.name

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

        # connect each tasks to the pyro daemon, for remote access
        for task in self.task_list:
            uri = pyro_daemon.connect( task, task.identity() )

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

        finished = []
        #state.reset()

        # if no tasks present, then we've incremented reference time and
        # deleted the old tasks (see below)
        if len( self.task_list ) == 0:
            self.create_tasks()


        # task interaction to satisfy prerequisites
        for task in self.task_list:
            task.get_satisfaction( self.task_list )
            task.run_if_satisfied()
            finished.append( task.is_finished() )

        state.update( self.task_list )

        # if all tasks finished, increment reference time and delete the
        # old tasks
        if not False in finished:
            self.cycle_time.increment()
            del self.task_list[:]

        return 1  # return 1 to keep the pyro requestLoop going

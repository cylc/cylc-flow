#!/usr/bin/python

"""
Class to parse an EcoConnect controller config file and handle task
creation according to the resulting configuration parameters (lists of
task names for particular transitional reference times).
"""

from reference_time import reference_time
from vtasks_dummy import *
from status import status
from shared import pyro_daemon

import re
import sys

class task_manager:

    all_tasks = [ 'A', 'B', 'C', 'D', 'E', 'F', 'G' ]

    def __init__( self, reftime, filename = None ):

        print "Initialising Task Manager"
    
        # create a system status monitor and connect it to the pyro nameserver
        self.state = status()
        uri = pyro_daemon.connect( self.state, "state" )

        self.ordered_ref_times = []
        self.config_task_lists = {}
        self.task_list = []

        self.cycle_time = reference_time( reftime )

        if filename is None:
            self.config_supplied = False
            return

        self.config_supplied = True
        cfile = open( filename, 'r' )

        print "user task config file:"
        for line in cfile:

            print "  +  " + line,

            # skip full line comments
            if re.compile( "^#" ).match( line ):
                continue

            # skip blank lines
            if re.compile( "^\s*$" ).match( line ):
                continue

            # line format: "YYYYMMDDHH [task list]"
            tokens = line.split()
            ref_time = reference_time( tokens[0] )
            foo = tokens[1:]

            # check tasks are known
            for task in foo:
                if not task in task_manager.all_tasks:
                    if task != "stop" and task != "all":
                        print "ERROR: unknown task ", task
                        sys.exit(1)

            # add to task_list dict
            self.config_task_lists[ ref_time ] = foo

        print

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

        if in_utero[0] == 'stop':
            print "> STOP requested for", self.cycle_time.to_str()
            in_utero = []

        self.task_list = []
        for task_name in in_utero:
            if task_name == 'A':
                self.task_list.append( A( self.cycle_time )) 
            elif task_name == 'B':
                self.task_list.append( B( self.cycle_time ))
            elif task_name == 'C':
                self.task_list.append( C( self.cycle_time ))
            elif task_name == 'D':
                self.task_list.append( D( self.cycle_time )) 
            elif task_name == 'E':
                self.task_list.append( E( self.cycle_time )) 
            elif task_name == 'F':
                self.task_list.append( F( self.cycle_time ))
            elif task_name == 'G':
                self.task_list.append( G( self.cycle_time ))
            else:
                print "ERROR: unknown task name", task_name
                # TO DO: handle errors

        consistent = True
        print
        print "Task List for " + self.cycle_time.to_str() + ":"
        for task_name in in_utero:
            print " + " + task_name

        print
        for task in self.task_list:
            if not task.will_get_satisfaction( self.task_list ):
                print "   " + task.identity() + " has ummatched prerequisites!"
                consistent = False

        if not consistent:
            print
            print "WARNING: one or more task's have pre-requisites that are not"
            print "         matched by other tasks' post-requisites."
            print "THESE TASKS WILL NEVER RUN unless their prerequisites are"
            print "         are satisfied by other means."
            print "TO DO: provide manual Pyro access to tasks for this purpose"
            print "         (e.g. for when it's known that a task completed in a"
            print "         previous run) and/or ability to set tasks \"(done)\""
            print "         via the config file."

        for task in self.task_list:
            uri = pyro_daemon.connect( task, task.identity() )


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
        
        finished = []
        self.state.reset()

        if len( self.task_list ) == 0:
            self.create_tasks()

        if len( self.task_list ) == 0:
            # still no tasks means we've reached the end
            print "No tasks created for ", self.cycle_time.to_str()
            print "STOPPING NOW"
            sys.exit(0)

        self.state.update( self.cycle_time.to_str() )

        for task in self.task_list:
            task.get_satisfaction( self.task_list )
            task.run_if_satisfied()
            self.state.update( task.get_status() )
            finished.append( task.finished )

        self.state.update_finished() 

        if not False in finished:
            self.cycle_time.increment()
            del self.task_list[:]

        return 1  # required return value for the pyro requestLoop call

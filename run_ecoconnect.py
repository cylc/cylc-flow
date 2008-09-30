#!/usr/bin/python

"""
========= ECOCONNECT CONTROLLER WITH IMPLICIT SCHEDULING ===============
                    Hilary Oliver, NIWA, 2008
                   See repository documentation
"""

import dclock

import Pyro.core
import Pyro.naming

import reference_time
from tasks import *
import shared 
from class_from_module import class_from_module
from task_config import task_config
from dead_letter_box import dead_letter_box
import threading

from system_status import system_status
from copy import deepcopy

import logging
import logging.handlers

import re
import sys
import Pyro.core

"""Class to parse an EcoConnect controller config file and handle task
creation according to the resulting configuration parameters (lists of
task names for particular transitional reference times)."""

class task_manager ( Pyro.core.ObjBase ):

    def __init__( self, ref_time, filename = None ):
        log.debug("initialising task manager")

        Pyro.core.ObjBase.__init__(self)
    
        self.initial_ref_time = ref_time
        self.config = task_config( filename )
        self.task_list = []

        # Start a Pyro nameserver in its own thread
        # (alternatively, run the 'pyro-ns' script as a separate process)
        log.debug( "starting pyro nameserver" )
        ns_starter = Pyro.naming.NameServerStarter()
        ns_thread = threading.Thread( target = ns_starter.start )
        ns_thread.setDaemon(True)
        ns_thread.start()
        ns_starter.waitUntilStarted(10)
        # locate the Pyro nameserver
        pyro_nameserver = Pyro.naming.NameServerLocator().getNS()
        self.pyro_daemon = Pyro.core.Daemon()
        self.pyro_daemon.useNameServer(pyro_nameserver)

        # connect the system status monitor to the pyro nameserver
        self.state = system_status()
        uri = self.pyro_daemon.connect( self.state, "state" )

        # dead letter box for use by external tasks
        self.dead_letter_box = dead_letter_box()
        uri = self.pyro_daemon.connect( self.dead_letter_box, "dead_letter_box" )


    def parse_config_file( self, filename ):
        self.config.parse_file( filename )


    def create_task_by_name( self, task_name, ref_time, state = "waiting" ):
        task = class_from_module( "tasks", task_name )( ref_time, state )
        hour = ref_time[8:10]
        if hour not in task.get_valid_hours():
            log.debug( task_name + " not valid for " + hour  )
        else:
            log.info( "Creating " + task_name + "for " + ref_time )
            self.task_list.append( task )
            # connect new task to the pyro daemon
            uri = self.pyro_daemon.connect( task, task.identity() )

            # if using an external pyro nameserver, unregister
            # objects from previous runs first:
            #try:
            #    self.pyro_daemon.disconnect( task )
            #except NamingError:
            #    pass


    def create_tasks( self, ref_time ):
        # create any tasks configured for ref_time that don't already exist
        # NOTE: THIS WILL NOT CREATE TASKS FOR A REFERENCE TIME THAT IS
        # NEVER REACHED BY ABDICATION OF PREVIOUS-REFERENCE-TIME TASKS.
        configured_tasks = self.config.get_config( ref_time )

        for task_name in configured_tasks:
            id = task_name + "_" + ref_time
            if id not in [ task.identity() for task in self.task_list ]:
                state = None
                if re.compile( "^.*:").match( task_name ):
                    [task_name, state] = task_name.split(':')

                self.create_task_by_name( task_name, ref_time, state )


    #def check_for_dead_soldiers( self ):

    #    DISABLED: NOT USEFUL IN CURRENT TASK MANAGEMENT SCHEME
    #    TASKS DEPENDENT ON DOWNLOADER, for instance, CAN NOW BE CREATED
    #    BEFORE THE DOWNLOADER ITSELF IS CREATED.

    #    # check that all existing tasks can have their prerequisites
    #    # satisfied by other existing tasks
    #    dead_soldiers = []
    #    for task in self.task_list:
    #        if not task.will_get_satisfaction( self.task_list ):
    #            dead_soldiers.append( task )
    #
    #    if len( dead_soldiers ) != 0:
    #        print "ERROR: THIS TASK LIST IS NOT SELF-CONSISTENT, i.e. one"
    #        print "or more tasks have pre-requisites that are not matched"
    #        print "by others post-requisites, THEREFORE THEY WILL NOT RUN"
    #        for soldier in dead_soldiers:
    #            print " + ", soldier.identity()
    #
    #        sys.exit(1)


    def run( self ):

        # Process once to start any tasks that have no prerequisites
        # We need at least one of these to start the system rolling 
        # (i.e. the downloader).  Thereafter things only happen only
        # when a running task gets a message via pyro). 
        self.create_tasks( self.initial_ref_time )
        self.process_tasks()

        # process tasks again each time a request is handled
        self.pyro_daemon.requestLoop( self.process_tasks )

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
            log.critical( "ALL TASKS DONE" )
            sys.exit(0)

        # lists to determine what's finished for each ref time
        all_finished = []
        running_ref_times = []

        # task interaction to satisfy prerequisites
        for task in self.task_list:
            task.get_satisfaction( self.task_list )
            task.run_if_ready()

            # create a new task foo(T+1) if foo(T) just finished
            if task.abdicate():
                task_name = task.name
                next_rt = reference_time.increment( task.ref_time, task.ref_time_increment )

                self.create_tasks( next_rt )
                #self.create_task_by_name( task_name, next_rt, statex )
         

            # delete any reference-time-batch of tasks that are (a) all
            # finished, and (b) older than the oldest running task.

            if task.ref_time not in finished.keys():
                finished[ task.ref_time ] = [ task.is_finished() ]
            else:
                finished[ task.ref_time ].append( task.is_finished() )

            if task.is_running():
                running_ref_times.append( task.ref_time )

        # delete all tasks for a given ref time if they've all finished 
        running_ref_times.sort( key = int )
        oldest_running_ref_time = running_ref_times[0]
        
        remove = []
        for rt in finished.keys():
            if int( rt ) < int( oldest_running_ref_time ):
                if False not in finished[rt]:
                    for task in self.task_list:
                        if task.ref_time == rt:
                            remove.append( task )

        if len( remove ) > 0:
            for task in remove:
                log.debug( "removing spent " + task.name + " for " + task.ref_time )
                self.task_list.remove( task )
                self.pyro_daemon.disconnect( task )

        del remove
   
        #    next_task_list = self.config.get_config( next_rt )

        self.state.update( self.task_list )

        return 1  # to keep the pyro requestLoop going


#----------------------------------------------------------------------

if __name__ == "__main__":
    # check command line arguments
    n_args = len( sys.argv ) - 1

    if n_args < 1 or n_args > 2 :
        print "USAGE:", sys.argv[0], "<REFERENCE_TIME> [<config file>]"
        sys.exit(1)

    initial_reference_time = sys.argv[1]
    task_config_file = None
    if n_args == 2: task_config_file = sys.argv[2]

    print
    print "__________________________________________________________"
    print "      .                                           ."
    print "      . EcoConnect Implicit Scheduling Controller ."
    print "__________________________________________________________"
    print
    print "Initial Reference Time " + sys.argv[1] 

    # configure a main logger
    log = logging.getLogger( "main" )
    log.setLevel( logging.DEBUG )
    max_bytes = 10000
    backups = 5
    h = logging.handlers.RotatingFileHandler( 
            'LOGFILES/main', 'a', max_bytes, backups )
    f = logging.Formatter( '%(levelname)-10s %(name)-10s %(asctime)s %(message)s', '%a, %d %b %Y %H:%M:%S' )
    h.setFormatter(f)
    log.addHandler(h)

    # write warnings and worse to stderr as well as to the log
    h2 = logging.StreamHandler(sys.stderr)
    h2.setLevel( logging.WARNING )
    h2.setFormatter( f )
    log.addHandler(h2)

    log.info( 'Startup, initial reference time ' + initial_reference_time )

    if n_args == 1:
        log.warning( "No task config file, running ALL tasks" )

    #if shared.run_mode == 1:
    #    # dummy mode clock in its own thread
    #    shared.dummy_clock = dclock.dclock( sys.argv[1] )
    #    shared.dummy_clock.start()

    # initialise the task manager
    god = task_manager( initial_reference_time, task_config_file )
    # NEED TO CONNECT GOD TO PYRO NAMESERVER TO ALLOW EXTERNAL CONTROL 

    # start processing
    god.run()

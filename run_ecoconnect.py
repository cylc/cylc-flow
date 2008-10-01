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
import threading

from system_status import system_status
from copy import deepcopy

import logging
import logging.handlers

import re
import sys
import Pyro.core

class task_manager ( Pyro.core.ObjBase ):

    def __init__( self, start_time, task_list ):
        log.debug("initialising task manager")

        Pyro.core.ObjBase.__init__(self)
    
        self.start_time = start_time
        self.task_list = task_list        # list of task names
        self.task_pool = []               # list of interacting task objects

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


    def create_task_by_name( self, task_name, ref_time, state = "waiting" ):
        task = class_from_module( "tasks", task_name )( ref_time, state )
        log.info( "Created " + task_name + " for " + task.ref_time )
        self.task_pool.append( task )
        # connect new task to the pyro daemon
        uri = self.pyro_daemon.connect( task, task.identity() )
        # if using an external pyro nameserver, unregister
        # objects from previous runs first:
        #try:
        #    self.pyro_daemon.disconnect( task )
        #except NamingError:
        #    pass


    def create_initial_tasks( self ):

        # TO DO: reimplement user task config:
        # if re.compile( "^.*:").match( task_name ):
        #     [task_name, state] = task_name.split(':')

        for task_name in self.task_list:
            self.create_task_by_name( task_name, self.start_time )



    #def check_for_dead_soldiers( self ):
    #DISABLED: NOT USEFUL UNDER ABDICATION TASK MANAGEMENT
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
        self.create_initial_tasks()
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


        if len( self.task_pool ) == 0:
            log.critical( "ALL TASKS DONE" )
            sys.exit(0)

        finished_nzlamposts_exist = False
        finished_nzlamposts = []
        batch_finished = {}
        still_running = []

        # task interaction to satisfy prerequisites
        for task in self.task_pool:

            task.get_satisfaction( self.task_pool )

            task.run_if_ready( self.task_pool )


            # create a new task foo(T+1) if foo(T) just finished
            if task.abdicate():
                task_name = task.name
                self.create_task_by_name( task_name, task.next_ref_time() )

            # record some info to determine which task batches 
            # can be deleted (see documentation just below)

            # find any finished nzlampost tasks
            if task.name == "nzlampost" and task.state == "finishd":
                hour = task.ref_time[8:10]
                if hour == "06" or hour == "18":
                    finished_nzlamposts_exist = True
                    finished_nzlamposts.append( task.ref_time )

            # find which ref_time batches are all finished
            # (assume yes, set no if any running task found)
            if task.ref_time not in batch_finished.keys():
                batch_finished[ task.ref_time ] = True

            if not task.is_finished():
                batch_finished[ task.ref_time ] = False

            if task.is_running():
                still_running.append( task.ref_time )

        # DELETE SOME SPENT TASKS, defined as:
        #   (a) finished 
        #   (b) no longer needed to satisfy anyone else

        # Normal tasks can only run once any previous instance is
        # finished, so there is no explicit dependence on previous
        # cycles: i.e. we can delete any completely finished
        # batch that is older than the oldest running task.

        # HOWEVER, topnet can run ahead of nzlampost so long as the
        # "most recently generated topnet input file" is <= 24 hours
        # old. Nzlampost only generates topnet files at 06 and 18, so: 
        # if there is no running nzlampost, topnet will depend on the
        # most recent FINISHED 06 or 18 nzlampost, and we can delete
        # any finished batches older than that. 

        # I.E. cutoff is the older of most-recent-finished-nzlampost
        # and oldest running.

        still_running.sort( key = int )
        oldest_running = still_running[0]

        cutoff = oldest_running
        log.debug( " + oldest running " + cutoff )

        if finished_nzlamposts_exist:
            finished_nzlamposts.sort( key = int, reverse = True )
            most_recent_finished_nzlampost = finished_nzlamposts[0]

            log.debug( " + topnet needs " + most_recent_finished_nzlampost )

            if int( most_recent_finished_nzlampost ) < int( cutoff ): 
                cutoff = most_recent_finished_nzlampost

        log.debug( "keep tasks " + cutoff + " or newer")
        
        remove = []
        for rt in batch_finished.keys():
            if int( rt ) < int( cutoff ):
                if batch_finished[rt]:
                    for task in self.task_pool:
                        if task.ref_time == rt:
                            remove.append( task )

        if len( remove ) > 0:
            for task in remove:
                log.debug( "removing spent " + task.name + " for " + task.ref_time )
                self.task_pool.remove( task )
                self.pyro_daemon.disconnect( task )

        del remove
   
        self.state.update( self.task_pool )

        return 1  # to keep the pyro requestLoop going


#----------------------------------------------------------------------

"""
class to take incoming pyro messages that are not directed at a specific
task object (the sender can direct warning messages here if the desired
task object no longer exists, for example)
"""

class dead_letter_box( Pyro.core.ObjBase ):

    def __init__( self ):
        log.debug( "Initialising Dead Letter Box" )
        Pyro.core.ObjBase.__init__(self)

    def incoming( self, message ):
        log.warning( "DEAD LETTER: " + message )

#----------------------------------------------------------------------

if __name__ == "__main__":
    # check command line arguments
    n_args = len( sys.argv ) - 1

    def usage():
        print "USAGE:", sys.argv[0], "[<start ref time>] [<config file>]"
        print ""
        print "(i) start time only: run all tasks from start time"
        print "(ii) config file only: run the configured tasks from"
        print "     the configured start time"
        print "(iii) both: run the configured tasks, but override the"
        print "     configure start time"


    print
    print "__________________________________________________________"
    print "      .                                           ."
    print "      . EcoConnect Implicit Scheduling Controller ."
    print "__________________________________________________________"
    print
    
    start_time_arg = None
    config_file = None
    
    if n_args == 2:
        start_time_arg = sys.argv[1]
        config_file = sys.argv[2]

    elif n_args == 1:
        arg = sys.argv[1]
        if reference_time.is_valid( arg ):
            start_time_arg = arg
        elif os.path.exists( arg ):
            config_file = arg
        else:
            usage()
            sys.exit(1)

    else: 
        usage()
        sys.exit(1)

    if config_file:
        print "config file: " + config_file
        # strip of the '.py'
        m = re.compile( "^(.*)\.py$" ).match( config_file )
        modname = m.groups()[0]
        # load the config file
        exec "from " + modname + " import start_time, task_list"

    else:
        print "no config file, running all tasks"
        task_list = all_tasks

    if start_time_arg:
        # override config file start_time
        start_time = start_time_arg


    # set up logging
    if not os.path.exists( 'LOGFILES' ):
        os.makedirs( 'LOGFILES' )

    log = logging.getLogger( "ecoconnect" )
    log.setLevel( logging.DEBUG )
    max_bytes = 10000
    backups = 5
    h = logging.handlers.RotatingFileHandler( 'LOGFILES/ecoconnect', 'a', max_bytes, backups )
    f = logging.Formatter( '%(asctime)s %(levelname)-8s - %(message)s', '%Y/%m/%d %H:%M:%S' )
    # use '%(name)-30s' to get the logger name print too 
    h.setFormatter(f)
    log.addHandler(h)


    # write warnings and worse to stderr as well as to the log
    h2 = logging.StreamHandler(sys.stderr)
    h2.setLevel( logging.WARNING )
    h2.setFormatter( f )
    log.addHandler(h2)


    # task-name-specific logs for ALL tasks 
    # these propagate messages up to the main log
    for name in all_tasks:
        foo = logging.getLogger( "ecoconnect." + name )

        h = logging.handlers.RotatingFileHandler( 'LOGFILES/' + name, 'a', max_bytes, backups )
        f = logging.Formatter( '%(asctime)s %(levelname)-8s - %(message)s', '%Y/%m/%d %H:%M:%S' )
        h.setFormatter(f)
        foo.addHandler(h)

    print 'Start time ' + start_time
    log.info( 'Start time ' + start_time )

    #if shared.run_mode == 1:
    #    # dummy mode clock in its own thread
    #    shared.dummy_clock = dclock.dclock( sys.argv[1] )
    #    shared.dummy_clock.start()

    # initialise the task manager
    god = task_manager( start_time, task_list )
    # NEED TO CONNECT GOD TO PYRO NAMESERVER TO ALLOW EXTERNAL CONTROL 

    # start processing
    god.run()

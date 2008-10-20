#!/usr/bin/python

"""
|----------------------------------------------------------------------|
|----------| ECOCONNECT CONTROLLER WITH IMPLICIT SEQUENCING |----------|
|----------------------------------------------------------------------|
                    Hilary Oliver, NIWA, 2008
                   See repository documentation

       Requires an external Pyro nameserver (start with 'pyro-ns')
"""

# Note that we can run the Pyro nameserver in a thread in this program:
#import threading
#ns_starter = Pyro.naming.NameServerStarter()
#ns_thread = threading.Thread( target = ns_starter.start )
#ns_thread.setDaemon(True)
#ns_thread.start()
#ns_starter.waitUntilStarted(10)

# Note: to put modules in sub-directories, add to search path like this:
# pwd = os.environ[ 'PWD' ]
# sys.path.insert(1, pwd + '/sub-dir-1' )

import Pyro.core, Pyro.naming
from Pyro.errors import NamingError

import reference_time
from get_instance import *
from dummy_clock import *
from pyro_ns_naming import *
from task_definitions import task_base 

import logging, logging.handlers
import sys, os, re

import config

#from config import logging_level
#from config import start_time, stop_time
#from config import task_list, dummy_out
#from config import dummy_mode, dummy_clock_rate, dummy_clock_offset

import pdb

#----------------------------------------------------------------------
class LogFilter(logging.Filter):
    # replace log message timestamps with dummy clock times

    def __init__(self, dclock, name = "" ):
        logging.Filter.__init__( self, name )
        self.dummy_clock = dclock

    def filter(self, record):
        # replace log message time stamp with dummy time
        record.created = self.dummy_clock.get_epoch()
        return True

#----------------------------------------------------------------------
class task_manager ( Pyro.core.ObjBase ):

    def __init__( self ):
        #log.debug("initialising task manager")

        Pyro.core.ObjBase.__init__(self)
    
        if config.dummy_mode:
            pyro_daemon.connect( dummy_clock, pyro_ns_name( 'dummy_clock' ) )

        self.task_pool = []               # list of interacting task objects

        self.state_dump_dir = 'STATE'
        if not os.path.exists( self.state_dump_dir ):
            os.makedirs( self.state_dump_dir )

        self.pause_requested = False
        self.shutdown_requested = False

        # dead letter box for use by external tasks
        self.dead_letter_box = dead_letter_box()

        pyro_daemon.connect( self.dead_letter_box, pyro_ns_name( 'dead_letter_box' ) )


    def create_task_by_name( self, task_name, ref_time, state = "waiting" ):

        # class creation can increase the reference time so can't check
        # for stop until after creation
        task = get_instance( 'task_definitions', task_name )( ref_time, state )

        if config.stop_time:
            if int( task.ref_time ) > int( config.stop_time ):
                task.log.info( task.name + " STOPPING at " + config.stop_time )
                del task
                return

        task.log.info( "New task created for " + task.ref_time )
        self.task_pool.append( task )

        # connect new task to the pyro daemon
        pyro_daemon.connect( task, pyro_ns_name( task.identity ) )

    def create_initial_tasks( self ):

        for task_name in config.task_list:
            state = None
            if re.compile( "^.*:").match( task_name ):
                [task_name, state] = task_name.split(':')

            self.create_task_by_name( task_name, config.start_time, state )


    def remove_dead_soldiers( self ):
        # Remove any tasks in the OLDEST BATCH whose prerequisites
        # cannot be satisfied by their co-temporal peers.  It's not
        # possible to detect dead soldiers in newer batches because 
        # the batch may not be fully populated yet(more tasks may appear
        # as their predecessors abdicate).

        # This is needed because, for example, if we start the system at
        # 12Z with topnet turned on, topnet is valid at every hour from 
        # 12 through 17Z, so those tasks will be created but they will 
        # never be able to run due to lack of any upstream nzlam_post
        # task until 18Z comes along.

        # NOTE THAT DEAD SOLDIERS ARE REMOVED IN THE TASK INTERACTION
        # LOOP, SO SOMETIMES THEY MAY NOT GET ELIMINATED IMMEDIATELY
        # ... just wait until a message comes in for another task. 

        batches = {}
        for task in self.task_pool:
            if task.ref_time not in batches.keys():
                batches[ task.ref_time ] = [ task ]
            else:
                batches[ task.ref_time ].append( task )

        reftimes = batches.keys()
        reftimes.sort( key = int )
        oldest_rt = reftimes[0]

        dead_soldiers = []
        for task in batches[ oldest_rt ]:
            if not task.will_get_satisfaction( batches[ oldest_rt ] ):
                dead_soldiers.append( task )
    
        for task in dead_soldiers:
            task.log.info( "abdicating a dead soldier " + task.identity )
            self.create_task_by_name( task.name, task.next_ref_time() )
            self.task_pool.remove( task )
            pyro_daemon.disconnect( task )

            del task


    def run( self ):

        self.create_initial_tasks()

        while True:
            # MAIN MESSAGE HANDLING LOOP

            if self.shutdown_requested:
                self.system_halt( 'by request' )
 
            if task_base.processing_required and not self.pause_requested:
                # TASK PROCESSING
                self.create_new_tasks()
                self.process_tasks()
                self.stop_if_done()
                self.kill_spent_tasks()
                self.remove_dead_soldiers()
                self.dump_state()

            task_base.processing_required = False
            # REMOTE OBJECT MESSAGE HANDLING
            pyro_daemon.handleRequests( timeout = None )


    def stop_if_done( self ):
        all_done = True
        for task in self.task_pool:
            if task.is_running():
                all_done = False
        if all_done:
            self.system_halt( 'ALL TASKS DONE' )

    def system_halt( self, message ):
        log.critical( 'System Halt: ' + message )
        pyro_daemon.shutdown( True ) 
        sys.exit(0)

    def create_new_tasks( self ):
        for task in self.task_pool:
            # create a new task(T+1) if task(T) has just finished
            if task.abdicate():
                task.log.debug( "abdicating " + task.identity )
                self.create_task_by_name( task.name, task.next_ref_time() )

    def process_tasks( self ):

        # MAIN TASK PROCESSING LOOP
        for task in self.task_pool:                  # LOOP OVER ALL TASKS

            task.get_satisfaction( self.task_pool )  # TASK INTERACTION
            task.run_if_ready( self.task_pool )      # RUN IF READY

    def kill_spent_tasks( self ):
        # DELETE tasks that are finished AND no longer needed to satisfy
        # the prerequisites of other waiting tasks.
        batch_finished = []
        cutoff_times = []
        for task in self.task_pool:   
            if task.state != 'finished':
                cutoff_times.append( task.get_cutoff( self.task_pool ))
            # which ref_time batches are all finished
            if task.ref_time not in batch_finished:
                batch_finished.append( task.ref_time )

        if len( cutoff_times ) == 0:
            # no tasks to delete (is this possible?)
            return

        cutoff_times.sort( key = int )
        cutoff = cutoff_times[0]

        log.debug( "task deletion cutoff is " + cutoff )

        remove_these = []
        for rt in batch_finished:
            if int( rt ) < int( cutoff ):
                log.debug( "REMOVING BATCH " + rt )
                for task in self.task_pool:
                    if task.ref_time == rt:
                        remove_these.append( task )

        if len( remove_these ) > 0:
            for task in remove_these:
                log.debug( "removing spent " + task.identity )
                self.task_pool.remove( task )
                pyro_daemon.disconnect( task )

            del remove_these


    def request_pause( self ):
        # call remotely via Pyro
        log.warning( "system pause requested" )
        self.pause_requested = True

    def request_resume( self ):
        # call remotely via Pyro
        log.warning( "system resume requested" )
        self.pause_requested = False

    def request_shutdown( self ):
        # call remotely via Pyro
        log.warning( "system shutdown requested" )
        self.shutdown_requested = True

    def get_state_summary( self ):
        summary = {}
        for task in self.task_pool:
            postreqs = task.get_postrequisites()
            n_total = len( postreqs )
            n_satisfied = 0
            for key in postreqs.keys():
                if postreqs[ key ]:
                    n_satisfied += 1

            summary[ task.identity ] = [ task.state, str( n_satisfied), str(n_total), task.latest_message ]

        return summary

    def dump_state( self ):

        # TO DO: implement restart from dumped state capability 
        # Also, consider:
        #  (i) using 'pickle' to dump and read state, or
        #  (ii) writing a python source file similar to current startup config

        config = {}
        for task in self.task_pool:
            ref_time = task.ref_time
            state = task.name + ":" + task.state
            if ref_time in config.keys():
                config[ ref_time ].append( state )
            else:
                config[ ref_time ] = [ state ]

        FILE = open( self.state_dump_dir + '/state', 'w' )

        ref_times = config.keys()
        ref_times.sort( key = int )
        for rt in ref_times:
            FILE.write( rt + ' ' )
            for entry in config[ rt ]:
                FILE.write( entry + ' ' )

            FILE.write( '\n' )

        FILE.close()

#----------------------------------------------------------------------
class dead_letter_box( Pyro.core.ObjBase ):
    """
    class to take incoming pyro messages that are not directed at a
    specific task object (the sender can direct warning messages here if
    the desired task object no longer exists, for example)
    """

    def __init__( self ):
        log.debug( "Initialising Dead Letter Box" )
        Pyro.core.ObjBase.__init__(self)

    def incoming( self, message ):
        log.warning( "DEAD LETTER: " + message )

#----------------------------------------------------------------------
# TO DO: convert to main() function, see:
# http://www.artima.com/weblogs/viewpost.jsp?thread=4829
# requires some thought about global variables like 'log'

if __name__ == "__main__":

    print "__________________________________________________________"
    print
    print "      . EcoConnect Implicit Sequencing Controller ."
    print "__________________________________________________________"

    # Variables that must be defined in config.py:
    #  1. start_time ('yyyymmddhh')
    #  2. stop_time  ('yyyymmddhh', or None for no stop)
    #  3. dummy_mode (dummy out all tasks)
    #  4. dummy_clock_rate (seconds per simulated hour) 
    #  5. dummy_clock_offset (hours before start_time)
    #  6. task_list (tasks out of task_definitions module to run)
    #  7. dummy_out (tasks to dummy out even when dummy_mode is False)
    #  8. logging_level (logging.(INFO|DEBUG))
    #  9. pyro_ns_group (must be unique for each running controller)
    
    print
    print 'Initial reference time ' + config.start_time
    if config.stop_time:
        print 'Final reference time ' + config.stop_time

    if config.dummy_mode:
        dummy_clock = dummy_clock( config.start_time, config.dummy_clock_rate, config.dummy_clock_offset ) 

    print
    print "Logging to ./LOGFILES"

    if not os.path.exists( 'LOGFILES' ):
        os.makedirs( 'LOGFILES' )

    log = logging.getLogger( "main" )
    log.setLevel( config.logging_level )
    max_bytes = 1000000
    backups = 5
    main_logfile = 'LOGFILES/ecocontroller'
    h = logging.handlers.RotatingFileHandler( main_logfile, 'a', max_bytes, backups )
    # the above creates a zero-sized log file if one doesn't already exist
    if os.path.getsize( main_logfile ) > 0:
        print ' + rotating existing log:', main_logfile
        h.doRollover()

    f = logging.Formatter( '%(asctime)s %(levelname)-8s %(name)-16s - %(message)s', '%Y/%m/%d %H:%M:%S' )
    # use '%(name)-30s' to get the logger name print too 
    h.setFormatter(f)
    log.addHandler(h)

    # write warnings and worse to stderr as well as to the log
    h2 = logging.StreamHandler(sys.stderr)
    h2.setLevel( logging.WARNING )
    h2.setFormatter( f )
    log.addHandler(h2)
    if config.dummy_mode:
        # replace logged real time with dummy clock time 
        log.addFilter( LogFilter( dummy_clock, "main" ))

    # task-name-specific log files for all tasks 
    # these propagate messages up to the main log
    for name in config.task_list:
        if re.compile( "^.*:").match( name ):
            [name, state] = name.split( ':' )
        foo = logging.getLogger( "main." + name )
        foo.setLevel( config.logging_level )

        task_logfile = 'LOGFILES/' + name
        h = logging.handlers.RotatingFileHandler( task_logfile, 'a', max_bytes/10, backups )
        # the above creates a zero-sized log file if one doesn't already exist
        if os.path.getsize( task_logfile ) > 0:
            print ' + rotating existing log:', task_logfile
            h.doRollover()

        f = logging.Formatter( '%(asctime)s %(levelname)-8s - %(message)s', '%Y/%m/%d %H:%M:%S' )
        h.setFormatter(f)
        foo.addHandler(h)
        if config.dummy_mode:
            # replace logged real time with dummy clock time 
            foo.addFilter( LogFilter( dummy_clock, "main" ))

    log.info( 'initial reference time ' + config.start_time )
    log.info( 'final reference time ' + config.stop_time )

    """ This program relies on SINGLE THREADED operation.  Pyro is
    multithreaded by default so we explicitly disable threading: """

    Pyro.config.PYRO_MULTITHREADED = 0

    """In SINGLE THREADED PYRO, handleRequests() returns after EITHER a
    timeout has occurred OR at least one request (remote method call)
    was handled.  With "timeout = None" this allows us to process tasks
    ONLY after remote method invocations come in. Further, the
    processing_required boolean set in task_base.incoming() allows us to
    process tasks ONLY when a task changes state as a result of an
    incoming message, which minimizes non-useful output from the task
    processing loop (e.g. in dummy mode there are a lot of remote calls
    on the dummy clock object, which does not alter tasks at all). 

    In MULTITHREADED PYRO, handleRequests() returns immediately after
    creating a new request handling thread for a single remote object
    and thereafter remote method calls on that object come in
    asynchronously in the dedicated thread.  It is impossible(?) to make
    our main loop work properly like this because handleRequests will
    block until a new connection is made, even while messages from
    existing remote objects are coming in.  Tasks that are ready to run
    are only set running in the processing loop, so these will be
    delayed unnecessarily until handleRequests returns.  The only way
    out of this is to do task processing on a handleRequests timeout
    as well, which results in a lot of unnecessary task processing."""
 
    # locate the Pyro nameserver
    pyro_nameserver = Pyro.naming.NameServerLocator().getNS()

    # create a Pyro nameserver group based on the user's name
    try:
        # first delete any existing objects registered in my group name
        # (this avoids having to restart the nameserver every time we
        # run the controller, or otherwise having to disconnect
        # individual objects that already exist).  If running several
        # ecocontroller instances, each needs a different group name.
        print
        print "Removing any '" + pyro_ns_group + "' group from the Pyro nameserver"
        pyro_nameserver.deleteGroup( pyro_ns_group )
    except NamingError:
        print "(no such group registered)"
        pass

    pyro_nameserver.createGroup( pyro_ns_group )
    pyro_daemon = Pyro.core.Daemon()
    pyro_daemon.useNameServer(pyro_nameserver)

    # initialise the task manager

    # TO DO: MIGHT AS WELL INCORPORATE TASK_MANAGER INTO THE MAIN PROGRAM?

    god = task_manager()
    # connect to pyro nameserver to allow external control
    pyro_daemon.connect( god, pyro_ns_name( 'god' ) )

    # start processing
    print
    print "Beginning task processing now"
    if config.dummy_mode:
        print "   RUNNING IN DUMMY MODE"
    print
    god.run()

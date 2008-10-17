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

import Pyro.core
import Pyro.naming
from Pyro.errors import NamingError

import reference_time
from get_instance import get_instance
from dummy_clock import *
from pyro_ns_naming import *

from copy import deepcopy

import logging, logging.handlers

import sys, os

import re

import pdb

class LogFilter(logging.Filter):
    # use in dummy mode to replace log timestamps with dummy clock times

    def __init__(self, dclock, name = "" ):
        logging.Filter.__init__( self, name )
        self.dummy_clock = dclock

    def filter(self, record):
        # replace log message time stamp with dummy time
        record.created = self.dummy_clock.get_epoch()
        return True


class task_manager ( Pyro.core.ObjBase ):

    def __init__( self, start_time, task_list, dummy_mode ):
        log.debug("initialising task manager")

        Pyro.core.ObjBase.__init__(self)
    
        if dummy_mode:
            pyro_daemon.connect( dummy_clock, pyro_ns_name( 'dummy_clock' ) )

        self.start_time = start_time
        self.task_list = task_list        # list of task names
        self.task_pool = []               # list of interacting task objects

        self.state_dump_dir = 'STATE'
        if not os.path.exists( self.state_dump_dir ):
            os.makedirs( self.state_dump_dir )

        self.pause_requested = False
        self.shutdown_requested = False

        # dead letter box for use by external tasks
        self.dead_letter_box = dead_letter_box()

        pyro_daemon.connect( self.dead_letter_box, pyro_ns_name( 'dead_letter_box' ) )


    def in_dummy_mode( self ):
        return dummy_mode


    def create_task_by_name( self, task_name, ref_time, state = "waiting" ):

        # class creation can increase the reference time so can't check
        # for stop until after creation
        task = get_instance( task_definition_module, task_name )( ref_time, state )

        if stop_time:
            if int( task.ref_time ) > int( stop_time ):
                task.log.info( task.name + " STOPPING at " + stop_time )
                del task
                return

        task.log.info( "New task created for " + task.ref_time )
        self.task_pool.append( task )

        # connect new task to the pyro daemon
        pyro_daemon.connect( task, pyro_ns_name( task.identity ) )

    def create_initial_tasks( self ):

        for task_name in self.task_list:
            state = None
            if re.compile( "^.*:").match( task_name ):
                [task_name, state] = task_name.split(':')

            self.create_task_by_name( task_name, self.start_time, state )


    def remove_dead_soldiers( self ):
        # Remove any tasks in the OLDEST time batch whose prerequisites
        # cannot be satisfied by their co-temporal peers. 

        # This only works for the OLDEST batch; satisfiers can appear
        # later  by abdication in newer batches). 

        # This is useful, e.g., if we start the system at 12Z with
        # topnet turned on, because topnet cannot get input from the
        # 12Z nzlam.

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
            task.log.debug( "abdicating a dead soldier " + task.identity )
            self.create_task_by_name( task.name, task.next_ref_time() )
            self.task_pool.remove( task )
            pyro_daemon.disconnect( task )

            del task


    def run( self ):

        self.create_initial_tasks()

        while True:
            # MAIN MESSAGE HANDLING LOOP

            if task_base.processing_required:
                #print "processing ..."
                self.process_tasks()

            task_base.processing_required = False
            #print "handling requests ..."
            pyro_daemon.handleRequests( timeout = None )


    def system_halt( self, message ):
        log.critical( 'Halting NOW: ' + message )
        pyro_daemon.shutdown( True ) 
        sys.exit(0)


    def process_tasks( self ):

        if self.shutdown_requested:
            self.system_halt( 'by request' )
 
        if self.pause_requested:
            # no new tasks please
            return
       
        if len( self.task_pool ) == 0:
            self.system_halt('all configured tasks done')

        finished_nzlam_post_6_18_exist = False
        finished_nzlam_post_6_18 = []
        topnet_found = False
        topnet_time = []
        batch_finished = {}
        still_running = []

        for task in self.task_pool:
            # create a new task(T+1) if task(T) has just finished
            if task.abdicate():
                task.log.debug( "abdicating " + task.identity )
                self.create_task_by_name( task.name, task.next_ref_time() )

        # task interaction to satisfy prerequisites
        for task in self.task_pool:

            task.get_satisfaction( self.task_pool )

            task.run_if_ready( self.task_pool, dummy_mode, dummy_rate )

            # Determine which tasks can be deleted (documentation below)

            # Generally speaking we can remove any batch(T) older than
            # the oldest running task, BUT topnet's "fuzzy" dependence
            # on nzlam_post requires special handling (see below).

            # find any finished 6 or 18Z nzlam_post tasks
            if task.name == "nzlam_post" and task.state == "finished":
                hour = task.ref_time[8:10]
                if hour == "06" or hour == "18":
                    finished_nzlam_post_6_18_exist = True
                    finished_nzlam_post_6_18.append( task.ref_time )

            # find the running or waiting topnet
            if task.name == 'topnet' and task.state != 'finished':
                if topnet_found:
                    # should only be one running or waiting
                    log.warning( 'already found topnet!')

                topnet_found = True
                topnet_time = task.ref_time

            # find which ref_time batches are all finished
            # (assume yes, set no if any running task found)
            if task.ref_time not in batch_finished.keys():
                batch_finished[ task.ref_time ] = True

            if not task.is_finished():
                batch_finished[ task.ref_time ] = False

            if task.is_running():
                still_running.append( task.ref_time )

        # DELETE SPENT TASKS i.e. those that are finished AND no longer
        # needed to satisfy the prerequisites of other tasks that are
        # yet to run, i.e. any batch OLDER THAN:
        #   (i) the oldest running task
        #   (ii) the most recent finished nzlam_post 
        # because upcoming hourly topnet tasks may still need the most
        # recent finished nzlam_post.

        # For running topnet on /test off operational files, nzlam_post
        # takes the place of the downloader (no prerequisites) and is
        # able to run ahead of topnet.  To handle this we had to modify
        # the second condition:
        #   (ii) the most recent finished nzlam_post THAT IS OLDER THAN
        #        THE MOST RECENT TOPNET.


        if len( still_running ) == 0:
            log.critical( "ALL TASKS DONE" )
            sys.exit(0)

        still_running.sort( key = int )
        oldest_running = still_running[0]

        cutoff = oldest_running
        log.debug( "oldest running task: " + cutoff )

        if finished_nzlam_post_6_18_exist and topnet_found:
            finished_nzlam_post_6_18.sort( key = int, reverse = True )
            for nzp_time in finished_nzlam_post_6_18:
                if int( nzp_time ) < int( topnet_time ):
                    log.debug( "most recent finished 6 or 18Z nzlam_post older than topnet: " + nzp_time )
                    if int( nzp_time ) < int( cutoff ):
                        cutoff = nzp_time
                    break

        log.debug( " => keeping tasks " + cutoff + " and newer")
        
        remove_these = []
        for rt in batch_finished.keys():
            if int( rt ) < int( cutoff ):
                if batch_finished[rt]:
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

        self.remove_dead_soldiers()
   
        self.dump_state()


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
def usage( argv ):
    print "USAGE:", argv[0], "<config module name>"
    print "  E.g. '" + argv[0] + " foo' loads foo.py"

#----------------------------------------------------------------------
# TO DO: convert to main() function, see:
# http://www.artima.com/weblogs/viewpost.jsp?thread=4829
# requires some thought about global variables like 'log'

if __name__ == "__main__":

    # check command line arguments
    n_args = len( sys.argv ) - 1

    print "__________________________________________________________"
    print
    print "      . EcoConnect Implicit Sequencing Controller ."
    print "__________________________________________________________"
    
    # TO DO: better commandline parsing with optparse or getopt
    # (maybe not needed as most input is from the config file?)

    if n_args != 1:
        usage( sys.argv )
        sys.exit(1)

    # set some defaults

    start_time = None
    stop_time = None
    config_file = None

    task_definition_module = 'operational_tasks'

    dummy_mode = False
    dummy_offset = None  
    dummy_rate = 60 

    # load user config
    config_module = sys.argv[1]

    print
    print "Using config module " + config_module
    config_file = config_module + '.py'

    if not os.path.exists( config_file ):
        print
        print "File not found: " + config_file
        usage( sys.argv )
        sys.exit(1)

    exec "from " + config_module + " import *"

    # check compulsory input
    if not start_time:
        print
        print "ERROR: start_time not defined"
        sys.exit(1)

    if len( task_list ) == 0:
        print
        print "ERROR: no tasks configured"
        sys.exit(1)

    print
    print 'Initial reference time ' + start_time
    if stop_time:
        print 'Final reference time ' + stop_time

    if dummy_mode:
        dummy_clock = dummy_clock( start_time, dummy_rate, dummy_offset ) 

    # load task definition module
    print
    print 'Loading task definitions from ' + task_definition_module + '.py'
    exec "from " + task_definition_module + " import *"

    print
    print "Logging to ./LOGFILES"

    if not os.path.exists( 'LOGFILES' ):
        os.makedirs( 'LOGFILES' )

    log = logging.getLogger( "main" )
    log.setLevel( logging_level )
    max_bytes = 1000000
    backups = 5
    main_logfile = 'LOGFILES/ecocontroller'
    h = logging.handlers.RotatingFileHandler( main_logfile, 'a', max_bytes, backups )
    if os.path.exists( main_logfile ):
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
    if dummy_mode:
        # replace logged real time with dummy clock time 
        log.addFilter( LogFilter( dummy_clock, "main" ))

    # task-name-specific log files for all tasks 
    # these propagate messages up to the main log
    for name in task_list:
        if re.compile( "^.*:").match( name ):
            [name, state] = name.split( ':' )
        foo = logging.getLogger( "main." + name )
        foo.setLevel( logging_level )

        task_logfile = 'LOGFILES/' + name
        h = logging.handlers.RotatingFileHandler( task_logfile, 'a', max_bytes/10, backups )
        if os.path.exists( task_logfile ):
            print ' + rotating existing log:', task_logfile
            h.doRollover()

        f = logging.Formatter( '%(asctime)s %(levelname)-8s - %(message)s', '%Y/%m/%d %H:%M:%S' )
        h.setFormatter(f)
        foo.addHandler(h)
        if dummy_mode:
            # replace logged real time with dummy clock time 
            foo.addFilter( LogFilter( dummy_clock, "main" ))

    log.info( 'initial reference time ' + start_time )
    log.info( 'final reference time ' + stop_time )

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
        print "Unregistering any existing '" + pyro_ns_group + "' group in the Pyro nameserver"
        pyro_nameserver.deleteGroup( pyro_ns_group )
    except NamingError:
        print "(no such group registered)"
        pass

    pyro_nameserver.createGroup( pyro_ns_group )
    pyro_daemon = Pyro.core.Daemon()
    pyro_daemon.useNameServer(pyro_nameserver)

    # initialise the task manager
    god = task_manager( start_time, task_list, dummy_mode )
    # connect to pyro nameserver to allow external control
    pyro_daemon.connect( god, pyro_ns_name( 'god' ) )

    # start processing
    print
    print "Beginning task processing now"
    if dummy_mode:
        print "     (in dummy mode)"
    print
    god.run()

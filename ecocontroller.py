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
from task_pool import *

import logging, logging.handlers
import sys, os, re

import config

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
class dead_letter_box( Pyro.core.ObjBase ):

    def __init__( self ):
        Pyro.core.ObjBase.__init__(self)

    def incoming( self, message ):
        log.warning( "DEAD LETTER: " + message )

#----------------------------------------------------------------------
def system_halt( message ):
    log.critical( 'System Halt: ' + message )
    pyro_daemon.shutdown( True ) 
    sys.exit(0)

#----------------------------------------------------------------------
if __name__ == "__main__":
    # TO DO: convert to main() function, see:
    # http://www.artima.com/weblogs/viewpost.jsp?thread=4829
    # requires some thought about global variables like 'log'

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

    if config.dummy_mode:
        pyro_daemon.connect( dummy_clock, pyro_ns_name( 'dummy_clock' ) )

    tasks = task_pool( config.task_list, pyro_daemon )
    pyro_daemon.connect( tasks, pyro_ns_name( 'god' ) )

    # dead letter box for use by external tasks
    dead_letter_box = dead_letter_box()

    pyro_daemon.connect( dead_letter_box, pyro_ns_name( 'dead_letter_box' ) )

    print
    print "Beginning task processing now"
    if config.dummy_mode:
        print "   RUNNING IN DUMMY MODE"
    print
 
    while True: # MAIN LOOP ############

        if tasks.shuttingdown:
            system_halt( 'by request' )

        # TASK PROCESSING ##############
        # (run through each time a remote method message comes in)
        if task_base.processing_required and not tasks.paused:
            tasks.regenerate()
            tasks.interact()
            tasks.run_if_ready()
            if tasks.all_finished():
                system_halt( 'ALL TASKS FINISHED' )
            tasks.kill_spent_tasks()
            tasks.kill_lame_ducks()
            tasks.dump_state()

        task_base.processing_required = False
        # PYRO REQUEST HANDLING ########
        # (returns after each remote method call processed)
        pyro_daemon.handleRequests( timeout = None )




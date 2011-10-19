#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

##### TO DO: self.config.check_task_groups() #####

from task_types import task
from task_types import clocktriggered
from prerequisites.plain_prerequisites import plain_prerequisites
from hostname import hostname
import logging
import datetime
import port_scan
from cycle_time import ct
import pimp_my_logger
import accelerated_clock 
import re, os, sys, shutil
from rolling_archive import rolling_archive
from cylc_pyro_server import pyro_server
from state_summary import state_summary
from remote_switch import remote_switch
from passphrase import SecurityError
from OrderedDict import OrderedDict
from job_submission.job_submit import job_submit
from locking.lockserver import lockserver
from locking.suite_lock import suite_lock
from suite_id import identifier
from mkdir_p import mkdir_p
from config import config, SuiteConfigError
from cylc.registration import delimiter_re, localdb, RegistrationError
from broker import broker
from Pyro.errors import NamingError, ProtocolError

from CylcError import TaskNotFoundError, TaskStateError

try:
    import graphing
except:
    graphing_disabled = True
else:
    graphing_disabled = False

class scheduler(object):
    def __init__( self, is_restart=False ):
        # PROVIDE IN DERIVED CLASSES:
        # 1/ self.parser = OptionParser( usage )
        # 2/ load_tasks()

        # SUITE OWNER
        self.owner = os.environ['USER']

        # SUITE HOST
        self.host= hostname

        # STARTUP BANNER
        self.banner = {}

        # TASK POOLS
        self.cycling_tasks = []
        self.asynchronous_tasks = []

        # DEPENDENCY BROKER
        self.broker = broker()

        self.lock_acquired = False

        self.blocked = True 
        self.is_restart = is_restart

        # COMMANDLINE OPTIONS
        #DISABLED PRACTICE MODE self.parser.set_defaults( simulation_mode=False, practice_mode=False, debug=False )
        self.parser.set_defaults( simulation_mode=False, debug=False )

        self.graph_warned = {}

        self.parser.add_option( "--until", 
                help="Shut down after all tasks have PASSED this cycle time.",
                metavar="YYYYMMDDHH", action="store", dest="stop_time" )

        self.parser.add_option( "--hold", help="Hold (don't run tasks) "
                "immediately on starting.",
                action="store_true", default=False, dest="start_held" )

        self.parser.add_option( "--hold-after",
                help="Hold (don't run tasks) AFTER this cycle time.",
                metavar="YYYYMMDDHH", action="store", dest="hold_time" )

        self.parser.add_option( "-s", "--simulation-mode",
                help="Use dummy tasks that masquerade as the real thing, "
                "and accelerate the wall clock: get the scheduling right "
                "without having to run the real suite tasks.",
                action="store_true", dest="simulation_mode" )

        #DISABLED self.parser.add_option( "-p", "--practice-mode",
        #DISABLED         help="Clone an existing suite in simulation mode using new state "
        #DISABLED         "and logging directories to avoid corrupting the original. "
        #DISABLED         "Failed tasks will not be reset to waiting in the clone.",
        #DISABLED         action="store_true", dest="practice_mode" )

        self.parser.add_option( "--fail", help=\
                "(SIMULATION MODE) get the specified task to report failure and then abort.",
                metavar="NAME%YYYYMMDDHH", action="store", dest="failout_task_id" )

        self.parser.add_option( "--debug", help=\
                "Turn on 'debug' logging and full exception tracebacks.",
                action="store_true", dest="debug" )

        self.parser.add_option( "--timing", help=\
                "Turn on main task processing loop timing, which may be useful "
                "for testing very large suites of 1000+ tasks.",
                action="store_true", default=False, dest="timing" )

        self.parser.add_option( "--gcylc", help=\
                "(DO NOT USE THIS OPTION).",
                action="store_true", default=False, dest="gcylc" )

        self.parse_commandline()
        self.check_not_running_already()
        self.configure_suite()

        # RUNAHEAD LIMIT
        self.runahead_limit = self.config['scheduling']['runahead limit']

        self.print_banner()
        # LOAD TASK POOL ACCORDING TO STARTUP METHOD (PROVIDED IN DERIVED CLASSES) 
        self.asynchronous_task_list = self.config.get_asynchronous_task_name_list()
        self.load_tasks()
        self.initial_oldest_ctime = self.get_oldest_c_time()

        global graphing_disabled
        if not self.config['visualization']['run time graph']['enable']:
            graphing_disabled = True
        if not graphing_disabled:
            self.initialize_runtime_graph()

    def parse_commandline( self ):
        # SUITE NAME
        suite = self.args[0]

        # find location of the suite definition directory
        try:
            db = localdb()
            db.load_from_file()
            self.suite_dir, junk = db.get(suite)
            self.suiterc = db.getrc(suite)
            self.suite = db.unalias(suite)
        except RegistrationError,x:
            raise SystemExit(x)

        # MODE OF OPERATION (REAL, SIMULATION, practice)
        #DISABLED if self.options.simulation_mode and self.options.practice_mode:
        #DISABLED     parser.error( "Choose ONE of simulation or practice mode")
        if self.options.simulation_mode:
            self.banner['Mode of operation'] = 'SIMULATION'
            self.simulation_mode = True
            #DISABLED self.practice = False
        #DISABLED elif self.options.practice_mode:
        #DISABLED     self.banner['Mode of operation'] = 'SIMULATION (PRACTICE)'
        #DISABLED     self.simulation_mode = True
        #DISABLED     self.practice = True
        else:
            self.banner['Mode of operation'] = 'REAL'
            self.simulation_mode = False
            #DISABLED self.practice = False

        # LOGGING LEVEL
        if self.options.debug:
            self.logging_level = logging.DEBUG
        else:
            self.logging_level = logging.INFO

        if self.options.gcylc:
            self.gcylc = True
        else:
            self.gcylc = False

    def check_not_running_already( self ):
        # CHECK SUITE IS NOT ALREADY RUNNING (unless practice mode)
        try:
            port = port_scan.get_port( self.suite, self.owner, self.host )
        except port_scan.SuiteNotFoundError,x:
            # Suite Not Found: good - it's not running already!
            pass
        else:
            #DISABLED if self.options.practice_mode:
            #DISABLED     print "Continuing in Cylc Practice Mode"
            #DISABLED else:
            raise SystemExit( "ERROR: suite " + self.suite + " is already running")

    def configure_suite( self ):
        # LOAD SUITE CONFIG FILE
        self.config = config( self.suite, self.suiterc, simulation_mode=self.simulation_mode )
        self.config.create_directories()
        if self.config['cylc']['simulation mode only'] and not self.simulation_mode:
            raise SystemExit( "ERROR: this suite can only run in simulation mode (see suite.rc)" )

        # DETERMINE SUITE LOGGING AND STATE DUMP DIRECTORIES
        self.logging_dir = self.config['cylc']['logging']['directory']
        self.state_dump_dir = self.config['cylc']['state dumps']['directory']
        #DISABLED if self.practice:
        #DISABLED     self.logging_dir += '-practice'
        #DISABLED     self.state_dump_dir   += '-practice'

        self.banner[ 'Logging to' ] = self.logging_dir
        self.banner[ 'State dump' ] = self.state_dump_dir
        # state dump file
        self.state_dump_filename = os.path.join( self.state_dump_dir, 'state' )

        self.stop_task = None

        # START and STOP CYCLE TIMES
        self.stop_time = None
        self.stop_clock_time = None
        # (self.start_time is set already if provided on the command line).

        if self.is_restart:
            # May provide a stop time on the command line only
            if self.options.stop_time:
                self.stop_time = self.options.stop_time
 
        else:
            if not self.start_time:
                # No initial cycle time provided on the command line.
                if self.config['scheduling']['initial cycle time']:
                    # Use suite.rc initial cycle time, if one is defined.
                    self.start_time = str(self.config['scheduling']['initial cycle time'])
                if self.options.stop_time:
                    # But a final cycle time was provided on the command line.
                    # NOTE: this will have to be changed if we use a STOP
                    # arg instead of the '--until=STOP' option - then it
                    # will not be possible to use STOP without START. 
                    self.stop_time = self.options.stop_time
                elif self.config['scheduling']['final cycle time']:
                    # Use suite.rc final cycle time, if one is defined.
                    self.stop_time = str(self.config['scheduling']['final cycle time'])
            else:
                # An initial cycle time was provided on the command line
                # => also use command line final cycle time, if provided,
                # but otherwise don't use the suite.rc default stop time
                # (user may change start without considering stop cycle).
                if self.options.stop_time:
                    # stop time provided on the command line
                    try:
                        self.stop_time = ct( self.options.stop_time ).get()
                    except CycleTimeError, x:
                        raise SystemExit(x)

        if not self.start_time:
            print >> sys.stderr, 'WARNING: No initial cycle time provided - no cycling tasks will be loaded.'

        if self.stop_time:
            self.banner[ 'Stopping at' ] = self.stop_time

        # PAUSE TIME?
        self.hold_suite_now = False
        self.hold_time = None
        if self.options.hold_time:
            try:
                self.hold_time = ct( self.options.hold_time ).get()
            except CycleTimeError, x:
                raise SystemExit(x)
            #    self.parser.error( "invalid cycle time: " + self.hold_time )
            self.banner[ 'Pausing at' ] = self.hold_time

        # start in unblocked state
        self.blocked = False

        # USE LOCKSERVER?
        self.use_lockserver = self.config['cylc']['lockserver']['enable']
        if self.use_lockserver:
            # check that user is running a lockserver
            # DO THIS BEFORE CONFIGURING PYRO FOR THE SUITE
            # (else scan etc. will hang on the partially started suite).
            try:
                self.lockserver_port = lockserver( self.host ).get_port()
            except port_scan.SuiteNotFoundError, x:
                raise SystemExit( 'Lockserver not found. See \'cylc lockserver status\'')
 
        # CONFIGURE SUITE PYRO SERVER
        #DISABLED if self.practice:
        #DISABLED     # modify suite name so we can run next to the original suite.
        #DISABLED     suitename = self.suite + "-practice"
        #DISABLED else:
        suitename = self.suite
        try:
            self.pyro = pyro_server( suitename, use_passphrase=self.config['cylc']['use secure passphrase'] )
        except SecurityError, x:
            print >> sys.stderr, 'SECURITY ERROR (secure passphrase problem)'
            raise SystemExit( str(x) )
        self.port = self.pyro.get_port()
        self.banner[ 'Listening on port' ] = self.port

        # REMOTELY ACCESSIBLE SUITE IDENTIFIER
        suite_id = identifier( self.suite, self.owner )
        self.pyro.connect( suite_id, 'cylcid', qualified = False )

        # REMOTELY ACCESSIBLE SUITE STATE SUMMARY
        self.suite_state = state_summary( self.config, self.simulation_mode, self.start_time, self.gcylc )
        self.pyro.connect( self.suite_state, 'state_summary')

        # USE QUICK TASK ELIMINATION?
        self.use_quick = self.config['development']['use quick task elimination'] 

        # ALLOW MULTIPLE SIMULTANEOUS INSTANCES?
        self.exclusive_suite_lock = not self.config['cylc']['lockserver']['simultaneous instances']

        # set suite in task class (for passing to hook scripts)
        task.task.suite = self.suite

        # Running in UTC time? (else just use the system clock)
        utc = self.config['cylc']['UTC mode']

        # CYLC EXECUTION ENVIRONMENT
        cylcenv = OrderedDict()
        cylcenv[ 'CYLC_DIR' ] = os.environ[ 'CYLC_DIR' ]
        cylcenv[ 'CYLC_MODE' ] = 'scheduler'
        cylcenv[ 'CYLC_SUITE_HOST' ] =  str( self.host )
        cylcenv[ 'CYLC_SUITE_PORT' ] =  str( self.pyro.get_port())
        cylcenv[ 'CYLC_SUITE_REG_NAME' ] = self.suite
        cylcenv[ 'CYLC_SUITE_REG_PATH' ] = re.sub( delimiter_re, '/', self.suite )
        cylcenv[ 'CYLC_SUITE_DEF_PATH' ] = re.sub( os.environ['HOME'], '$HOME', self.suite_dir )
        cylcenv[ 'CYLC_SUITE_OWNER' ] = self.owner
        cylcenv[ 'CYLC_USE_LOCKSERVER' ] = str( self.use_lockserver )
        if self.use_lockserver:
            cylcenv[ 'CYLC_LOCKSERVER_PORT' ] = str( self.lockserver_port )
        cylcenv[ 'CYLC_UTC' ] = str(utc)

        # CLOCK (accelerated time in simulation mode)
        rate = self.config['cylc']['simulation mode']['clock rate']
        offset = self.config['cylc']['simulation mode']['clock offset']
        self.clock = accelerated_clock.clock( int(rate), int(offset), utc, self.simulation_mode ) 

        # nasty kludge to give the simulation mode clock to task classes:
        task.task.clock = self.clock
        clocktriggered.clocktriggered.clock = self.clock

        self.pyro.connect( self.clock, 'clock' )

        self.failout_task_id = self.options.failout_task_id

        # JOB SUBMISSION
        job_submit.simulation_mode = self.simulation_mode
        job_submit.cylc_env = cylcenv
        if self.simulation_mode and self.failout_task_id:
                job_submit.failout_id = self.failout_task_id

        # SCHEDULER ENVIRONMENT
        # Access to the suite bin directory for alert scripts executed
        # by the scheduler. 
        os.environ['PATH'] = self.suite_dir + '/bin:' + os.environ['PATH'] 
        # User defined local variables that may be required by alert scripts
        senv = self.config['cylc']['environment']
        for var in senv:
            os.environ[var] = os.path.expandvars(senv[var])

        # suite identity for alert scripts (which are executed by the scheduler).
        # Also put cylcenv variables in the scheduler environment
        for var in cylcenv:
            os.environ[var] = cylcenv[var]

        # LIST OF ALL TASK NAMES
        self.task_name_list = self.config.get_task_name_list()

        # PIMP THE SUITE LOG
        self.log = logging.getLogger( 'main' )
        pimp_my_logger.pimp_it( \
             self.log, self.logging_dir, self.config['cylc']['logging']['roll over at start-up'], \
                self.logging_level, self.clock )

        # STATE DUMP ROLLING ARCHIVE
        arclen = self.config[ 'cylc']['state dumps']['number of backups' ]
        self.state_dump_archive = rolling_archive( self.state_dump_filename, arclen )

        # REMOTE CONTROL INTERFACE
        # (note: passing in self to give access to task pool methods is a bit clunky?).
        self.remote = remote_switch( self.config, self.clock, self.suite_dir, self, self.failout_task_id )
        self.pyro.connect( self.remote, 'remote' )


    def print_banner( self ):
        #Nice, but doesn't print well in gui windows with non-monospace fonts:
        #print "_______________________________________________"
        #print "_ Cylc Self Organising Adaptive Metascheduler _"
        #print "_\    (c) Hilary Oliver, NIWA, 2008-2011     /_"
        #print "__\        cylc is pronounced 'silk'        /__"
        #print "___\________________C_Y_L_C________________/___"
        #print

        print ""
        print "THIS IS THE CYLC FORECAST SUITE METASCHEDULER"
        print "Copyright (C) 2008-2011 Hilary Oliver, NIWA"
        print ""
        print "This program comes with ABSOLUTELY NO WARRANTY;"
        print "for details type: `cylc license warranty'."
        print "This is free software, and you are welcome to "
        print "redistribute it under certain conditions;"
        print "for details type: `cylc license conditions'."
        print 

        items = self.banner.keys()

        longest_item = items[0]
        for item in items:
            if len(item) > len(longest_item):
                longest_item = item

        template = re.sub( '.', '.', longest_item )

        for item in self.banner.keys():
            print ' o ', re.sub( '^.{' + str(len(item))+ '}', item, template) + '...' + str( self.banner[ item ] )

    def back_up_statedump_file( self ):
       # back up the configured state dump (i.e. the one that will be used
       # by the suite unless in practice mode, but not necessarily the
       # initial one). 
       if os.path.exists( self.state_dump_filename ):
           backup = self.state_dump_filename + '.' + self.clock.get_datetime().isoformat()
           print "Backing up the state dump file:"
           print "  " + self.state_dump_filename + " --> " + backup
           try:
               shutil.copyfile( self.state_dump_filename, backup )
           except:
               raise SystemExit( "ERROR: State dump file copy failed" )

    def run( self ):
        if self.use_lockserver:
            #DISABLED if self.practice:
            #DISABLED     suitename = self.suite + '-practice'
            #DISABLED else:
            suitename = self.suite

            # request suite access from the lock server
            if suite_lock( suitename, self.suite_dir, self.host, self.lockserver_port, 'scheduler' ).request_suite_access( self.exclusive_suite_lock ):
               self.lock_acquired = True
            else:
               raise SystemExit( "Failed to acquire a suite lock" )

        #DISABLED if not self.practice:
        #DISABLED     self.back_up_statedump_file()

        if self.hold_time:
            # TO DO: HANDLE STOP AND PAUSE TIMES THE SAME WAY?
            self.hold_suite( self.hold_time )

        if self.options.start_held:
            self.log.warning( "Held on start-up (no tasks will be submitted)")
            self.hold_suite()
        else:
            print "\nSTARTING\n"

        while True: # MAIN LOOP
            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.

            if self.process_tasks():
                #print "ENTERING MAIN LOOP"
                if self.options.timing:
                    # loop timing: use real clock even in sim mode
                    main_loop_start_time = datetime.datetime.now()

                self.negotiate()
                self.run_tasks()
                self.cleanup()
                self.spawn()
                self.dump_state()

                self.suite_state.update( self.cycling_tasks, self.asynchronous_tasks, self.clock, \
                        self.get_oldest_c_time(), self.get_newest_c_time(),
                        self.paused(), self.will_pause_at(), \
                        self.remote.halt, self.will_stop_at(), self.blocked )

                if self.options.timing:
                    delta = datetime.datetime.now() - main_loop_start_time
                    seconds = delta.seconds + float(delta.microseconds)/10**6
                    print "MAIN LOOP TIME TAKEN:", seconds, "seconds"

            # SHUT DOWN IF ALL TASKS ARE SUCCEEDED OR HELD
            stop_now = True  # assume stopping
            #for itask in self.asynchronous_tasks:
            #    if not itask.state.is_succeeded() and not itask.state.is_held():
            #        # don't stop if any tasks are waiting, submitted, or running
            #        stop_now = False
            #        break

            #if stop_now:                 
            if True:
                if self.hold_suite_now or self.hold_time:
                    # don't stop if the suite is held
                    stop_now = False
                for itask in self.cycling_tasks + self.asynchronous_tasks:
                    # find any reason not to stop
                    if not itask.state.is_succeeded() and not itask.state.is_held():
                        # don't stop if any tasks are waiting, submitted, or running
                        stop_now = False
                        break
                for itask in self.cycling_tasks:
                    if itask.state.is_succeeded() and not itask.state.has_spawned():
                        # Check for tasks that are succeeded but not spawned.
                        # If they are older than the suite stop time they
                        # must be about to spawn. Otherwise they must be 
                        # stalled at the runahead limit, in which case we
                        # can stop.
                        if self.stop_time:
                            if int(itask.tag) < int(self.stop_time):
                                stop_now = False
                                break
                        else:
                            stop_now = False
                            break

            if stop_now:
                self.log.warning( "ALL TASKS FINISHED OR HELD" )
                break

            if self.remote.halt and self.no_tasks_running():
                self.log.warning( "ALL RUNNING TASKS FINISHED" )
                break

            if self.remote.halt_now:
                if not self.no_tasks_running():
                    self.log.warning( "STOPPING NOW: some running tasks will be orphaned" )
                break

            if self.stop_clock_time:
                now = self.clock.get_datetime()
                if now > self.stop_clock_time:
                    self.log.warning( "SUITE STOP TIME REACHED: " + self.stop_clock_time.isoformat() )
                    self.hold_suite()
                    self.remote.halt = True
                    # now reset self.stop_clock_time so we don't do this check again.
                    self.stop_clock_time = None

            if self.stop_task:
                name, tag = self.stop_task.split('%')
                # shut down if task type name has entirely passed task
                stop = True
                for itask in self.cycling_tasks + self.asynchronous_tasks:
                    if itask.name == name:
                        if not itask.state.is_succeeded():
                            iname, itag = itask.id.split('%')
                            if int(itag) <= int(tag):
                                stop = False
                if stop:
                    self.log.warning( "No unfinished STOP TASK (" + name + ") older than " + tag + " remains" )
                    self.hold_suite()
                    self.remote.halt = True
                    # now reset self.stop_task so we don't do this check again.
                    self.stop_task = None

            self.check_timeouts()
            self.release_runahead()

            # REMOTE METHOD HANDLING; with no timeout and single- threaded pyro,
            # handleRequests() returns after one or more remote method
            # invocations are processed (these are not just task messages, hence
            # the use of the state_changed variable above).
            # HOWEVER, we now need to check if clock-triggered tasks are ready
            # to trigger according on wall clock time, so we also need a
            # timeout to handle this when nothing else is happening.
            #--

            # incoming task messages set task.state_changed to True
            self.pyro.handleRequests(timeout=1)
        # END MAIN LOOP
        self.log.critical( "SHUTTING DOWN" )

    def process_tasks( self ):
        # do we need to do a pass through the main task processing loop?
        process = False
        if task.state_changed:
            # reset task.state_changed
            task.state_changed = False
            process = True
        elif self.remote.process_tasks:
            # reset the remote control flag
            self.remote.process_tasks = False
            process = True
        elif self.waiting_clocktriggered_task_ready():
            # This actually returns True if ANY task is ready to run,
            # not just clock-triggered tasks (but this should not matter).
            # For a clock-triggered task, this means its time offset is
            # up AND its prerequisites are satisfied; it won't result
            # in multiple passes through the main loop.
            process = True
        return process

    def shutdown( self ):
        # called by main command
        print "\nSTOPPING"

        if self.use_lockserver:
            # do this last
            #DISABLED if self.practice:
            #DISABLED     suitename = self.suite + '-practice'
            #DISABLED else:
            suitename = self.suite

            if self.lock_acquired:
                print "Releasing suite lock"
                lock = suite_lock( suitename, self.suite_dir, self.host, self.lockserver_port, 'scheduler' )
                if not lock.release_suite_access():
                    print >> sys.stderr, 'WARNING failed to release suite lock!'

        if self.pyro:
            self.pyro.shutdown()

        global graphing_disabled
        if not graphing_disabled:
            self.finalize_runtime_graph()

    def get_tasks( self ):
        return self.cycling_tasks + self.asynchronous_tasks

    def set_stop_ctime( self, stop_time ):
        self.log.warning( "Setting stop cycle time: " + stop_time )
        self.stop_time = stop_time

    def set_stop_clock( self, dtime ):
        self.log.warning( "Setting stop clock time: " + dtime.isoformat() )
        self.stop_clock_time = dtime

    def set_stop_task( self, taskid ):
        self.log.warning( "Setting stop task: " + taskid )
        self.stop_task = taskid

    def hold_suite( self, ctime = None ):
        #self.log.warning( 'pre-hold state dump: ' + self.dump_state( new_file = True ))
        if ctime:
            self.log.warning( "Setting suite hold cycle time: " + ctime )
            self.hold_time = ctime
        else:
            self.hold_suite_now = True
            self.log.warning( "Holding all tasks now")
            for itask in self.cycling_tasks + self.asynchronous_tasks:
                if itask.state.is_waiting() or itask.state.is_runahead():
                    itask.state.set_status('held')

    def release_suite( self ):
        if self.hold_suite_now:
            self.log.warning( "RELEASE: new tasks will run when ready")
            self.hold_suite_now = False
            self.hold_time = None
        for itask in self.cycling_tasks + self.asynchronous_tasks:
            if itask.state.is_held():
                itask.state.set_status('waiting')
 
        # TO DO: write a separate method for cancelling a stop time:
        #if self.stop_time:
        #    self.log.warning( "UNSTOP: unsetting suite stop time")
        #    self.stop_time = None

    def will_stop_at( self ):
        if self.stop_time:
            return self.stop_time
        elif self.stop_clock_time:
            return self.stop_clock_time.isoformat()
        elif self.stop_task:
            return self.stop_task
        else:
            return None

    def clear_stop_times( self ):
        self.stop_time = None
        self.stop_clock_time = None
        self.stop_task = None
 
    def paused( self ):
        return self.hold_suite_now

    def stopping( self ):
        if self.stop_time or self.stop_clock_time:
            return True
        else:
            return False

    def will_pause_at( self ):
        return self.hold_time

    def get_oldest_unfailed_c_time( self ):
        # return the cycle time of the oldest task
        oldest = '99991228235959'
        for itask in self.cycling_tasks:
            if itask.state.is_failed():
                continue
            #if itask.is_daemon():
            #    # avoid daemon tasks
            #    continue
            if int( itask.c_time ) < int( oldest ):
                oldest = itask.c_time
        return oldest

    def get_oldest_async_tag( self ):
        # return the tag of the oldest non-daemon task
        oldest = 9999999999
        for itask in self.asynchronous_tasks:
            #if itask.state.is_failed():  # uncomment for earliest NON-FAILED 
            #    continue
            if itask.is_daemon():
                continue
            if int( itask.tag ) < oldest:
                oldest = int(itask.tag)
        return oldest

    def get_oldest_c_time( self ):
        # return the cycle time of the oldest task
        oldest = '9999122823'
        for itask in self.cycling_tasks:
            #if itask.state.is_failed():  # uncomment for earliest NON-FAILED 
            #    continue
            #if itask.is_daemon():
            #    # avoid daemon tasks
            #    continue
            if int( itask.c_time ) < int( oldest ):
                oldest = itask.c_time
        return oldest

    def get_newest_c_time( self ):
        # return the cycle time of the newest task
        newest = ct('1000010101').get()
        for itask in self.cycling_tasks:
            # avoid daemon tasks
            #if itask.is_daemon():
            #    continue
            if int( itask.c_time ) > int( newest ):
                newest = itask.c_time
        return newest

    def no_tasks_running( self ):
        # return True if no REAL tasks are submitted or running
        #--
        for itask in self.cycling_tasks + self.asynchronous_tasks:
            if itask.state.is_running() or itask.state.is_submitted():
                if hasattr( itask, 'is_pseudo_task' ):
                    # ignore task families -their 'running' state just
                    # indicates existence of running family members.
                    continue
                else:
                    return False
        return True

    def negotiate( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        # BROKERED NEGOTIATION is O(n) in number of tasks.
        #--

        self.broker.reset()

        for itask in self.cycling_tasks + self.asynchronous_tasks:
            # register task outputs
            self.broker.register( itask )

        for itask in self.cycling_tasks + self.asynchronous_tasks:
            # try to satisfy me (itask) if I'm not already satisfied.
            if itask.not_fully_satisfied():
                self.broker.negotiate( itask )

        for itask in self.cycling_tasks + self.asynchronous_tasks:
            # This decides whether task families have succeeded or failed
            # based on the state of their members.
            if itask.state.is_succeeded() or itask.state.is_failed():
                # already decided
                continue
            if not itask.not_fully_satisfied():
                # families are not fully satisfied until all their
                # members have succeeded or failed. Only then can
                # we decide on the final family state, by checking
                # on its special family member prerequisites.
                itask.check_requisites()

    def release_runahead( self ):
        if self.runahead_limit:
            ouct = self.get_oldest_unfailed_c_time() 
            for itask in self.cycling_tasks:
                if itask.state.is_runahead():
                    foo = ct( itask.c_time )
                    foo.decrement( hours=self.runahead_limit )
                    if int( foo.get() ) < int( ouct ):
                        itask.log( 'DEBUG', "RELEASING (runahead limit)" )
                        itask.state.set_status('waiting')

    def run_tasks( self ):
        # tell each task to run if it is ready
        global graphing_disabled
        for itask in self.cycling_tasks:
            if itask.run_if_ready():
                if not graphing_disabled:
                    if not self.runtime_graph_finalized:
                        # add tasks to the runtime graph when they start running.
                        self.update_runtime_graph( itask )

        for itask in self.asynchronous_tasks:
            if itask.run_if_ready():
                if not graphing_disabled and not self.runtime_graph_finalized:
                    # add tasks to the runtime graph when they start running.
                    self.update_runtime_graph_async( itask )

    def check_hold_spawned_task( self, old_task, new_task ):
        if self.hold_suite_now:
            new_task.log( 'WARNING', "HOLDING (general suite hold) " )
            new_task.state.set_status('held')
        elif self.stop_time and int( new_task.c_time ) > int( self.stop_time ):
            # we've reached the suite stop time
            new_task.log( 'WARNING', "HOLDING (beyond suite stop cycle) " + self.stop_time )
            new_task.state.set_status('held')
        elif self.hold_time and int( new_task.c_time ) > int( self.hold_time ):
            # we've reached the suite hold time
            new_task.log( 'WARNING', "HOLDING (beyond suite hold cycle) " + self.hold_time )
            new_task.state.set_status('held')
        elif old_task.stop_c_time and int( new_task.c_time ) > int( old_task.stop_c_time ):
            # this task has a stop time configured, and we've reached it
            new_task.log( 'WARNING', "HOLDING (beyond task stop cycle) " + old_task.stop_c_time )
            new_task.state.set_status('held')
        elif self.runahead_limit:
            ouct = self.get_oldest_unfailed_c_time() 
            foo = ct( new_task.c_time )
            foo.decrement( hours=self.runahead_limit )
            if int( foo.get() ) >= int( ouct ):
                # beyond the runahead limit
                new_task.log( 'DEBUG', "HOLDING (runahead limit)" )
                new_task.state.set_status('runahead')

    def spawn( self ):
        # create new tasks foo(T+1) if foo has not got too far ahead of
        # the slowest task, and if foo(T) spawns

        for itask in self.cycling_tasks:
            if itask.ready_to_spawn():
                itask.log( 'DEBUG', 'spawning')
                # dynamic task object creation by task and module name
                new_task = itask.spawn( 'waiting' )
                self.check_hold_spawned_task( itask, new_task )
                # perpetuate the task stop time, if there is one
                new_task.stop_c_time = itask.stop_c_time
                self.insert( new_task )

        for itask in self.asynchronous_tasks:
            if itask.ready_to_spawn():
                itask.log( 'DEBUG', 'spawning')
                # dynamic task object creation by task and module name
                new_task = itask.spawn( 'waiting' )
                self.insert( new_task )

    def force_spawn( self, itask ):
        if itask.state.has_spawned():
            return None
        else:
            itask.state.set_spawned()
            itask.log( 'DEBUG', 'forced spawning')
            # dynamic task object creation by task and module name
            new_task = itask.spawn( 'waiting' )
            self.check_hold_spawned_task( itask, new_task )
            # perpetuate the task stop time, if there is one
            new_task.stop_c_time = itask.stop_c_time
            self.insert( new_task )
            return new_task

    def dump_state( self, new_file = False ):
        if new_file:
            filename = self.state_dump_filename + '.' + self.clock.dump_to_str()
            FILE = open( filename, 'w' )
        else:
            filename = self.state_dump_filename 
            FILE = self.state_dump_archive.roll_open()

        # suite time
        if self.simulation_mode:
            FILE.write( 'simulation time : ' + self.clock.dump_to_str() + ',' + str( self.clock.get_rate()) + '\n' )
        else:
            FILE.write( 'suite time : ' + self.clock.dump_to_str() + '\n' )

        if self.stop_time:
            FILE.write( 'stop time : ' + self.stop_time + '\n' )
        else:
            FILE.write( 'stop time : (none)\n' )

        for itask in self.cycling_tasks + self.asynchronous_tasks:
            # TO DO: CHECK THIS STILL WORKS 
            itask.dump_class_vars( FILE )
            # task instance variables
            itask.dump_state( FILE )

        FILE.close()
        # return the filename (minus path)
        return os.path.basename( filename )

    def earliest_unspawned( self ):
        all_spawned = True
        earliest_unspawned = '9999887766'
        for itask in self.cycling_tasks:
            if not itask.state.has_spawned():
                all_spawned = False
                if not earliest_unspawned:
                    earliest_unspawned = itask.c_time
                elif int( itask.c_time ) < int( earliest_unspawned ):
                    earliest_unspawned = itask.c_time

        return [ all_spawned, earliest_unspawned ]

    def earliest_unsatisfied( self ):
        # find the earliest unsatisfied task
        all_satisfied = True
        earliest_unsatisfied = '9999887766'
        for itask in self.cycling_tasks:
            if not itask.prerequisites.all_satisfied():
                all_satisfied = False
                if not earliest_unsatisfied:
                    earliest_unsatisfied = itask.c_time
                elif int( itask.c_time ) < int( earliest_unsatisfied ):
                    earliest_unsatisfied = itask.c_time

        return [ all_satisfied, earliest_unsatisfied ]

    def earliest_unsucceeded( self ):
        # find the earliest unsucceeded task
        # EXCLUDING FAILED TASKS
        all_succeeded = True
        earliest_unsucceeded = '9999887766'
        for itask in self.cycling_tasks:
            if itask.state.is_failed():
                # EXCLUDING FAILED TASKS
                continue
            #if itask.is_daemon():
            #   avoid daemon tasks
            #   continue

            if not itask.state.is_succeeded():
                all_succeeded = False
                if not earliest_unsucceeded:
                    earliest_unsucceeded = itask.c_time
                elif int( itask.c_time ) < int( earliest_unsucceeded ):
                    earliest_unsucceeded = itask.c_time

        return [ all_succeeded, earliest_unsucceeded ]

    def cleanup( self ):
        # Delete tasks that are no longer needed, i.e. those that
        # spawned, succeeded, AND are no longer needed to satisfy
        # the prerequisites of other tasks.
        #--

        # times of any failed tasks. 
        failed_rt = {}
        for itask in self.cycling_tasks:
            if itask.state.is_failed():
                failed_rt[ itask.c_time ] = True

        # suicide
        for itask in self.cycling_tasks + self.asynchronous_tasks:
            if itask.suicide_prerequisites.count() != 0:
                if itask.suicide_prerequisites.all_satisfied():
                    self.spawn_and_die( [itask.id], dump_state=False, reason='suicide' )

        if self.use_quick:
            self.cleanup_non_intercycle( failed_rt )

        self.cleanup_generic( failed_rt )

        self.cleanup_async()

    def async_cutoff(self):
        cutoff = 0
        for itask in self.asynchronous_tasks:
            if itask.is_daemon():
                # avoid daemon tasks
                continue
            if not itask.done():
                if itask.tag > cutoff:
                    cutoff = itask.tag
        return cutoff
 
    def cleanup_async( self ):
        cutoff = self.async_cutoff()
        spent = []
        for itask in self.asynchronous_tasks:
            if itask.done() and itask.tag < cutoff:
                spent.append( itask )
        for itask in spent:
            self.trash( itask, 'async spent' )

    def cleanup_non_intercycle( self, failed_rt ):
        # A/ Non INTERCYCLE tasks by definition have ONLY COTEMPORAL
        # DOWNSTREAM DEPENDANTS). i.e. they are no longer needed once
        # their cotemporal peers have succeeded AND there are no
        # unspawned tasks with earlier cycle times. So:
        #
        # (i) FREE TASKS are spent if they are:
        #    spawned, succeeded, no earlier unspawned tasks.
        #
        # (ii) TIED TASKS are spent if they are:
        #    spawned, succeeded, no earlier unspawned tasks, AND there is
        #    at least one subsequent instance that is SUCCEEDED
        #    ('satisfied' would do but that allows elimination of a tied
        #    task whose successor could subsequently fail, thus
        #    requiring manual task reset after a restart).
        #  ALTERNATIVE TO (ii): DO NOT ALLOW non-INTERCYCLE tied tasks
        #--

        # time of the earliest unspawned task
        [all_spawned, earliest_unspawned] = self.earliest_unspawned()
        if all_spawned:
            self.log.debug( "all tasks spawned")
        else:
            self.log.debug( "earliest unspawned task at: " + earliest_unspawned )

        # find the spent quick death tasks
        spent = []
        for itask in self.cycling_tasks:
            if itask.intercycle: 
                # task not up for consideration here
                continue
            if not itask.has_spawned():
                # task has not spawned yet, or will never spawn (one off tasks)
                continue
            if not itask.done():
                # task has not succeeded yet
                continue

            #if itask.c_time in failed_rt.keys():
            #    # task is cotemporal with a failed task
            #    # THIS IS NOT NECESSARY AS WE RESTART FAILED
            #    # TASKS IN THE READY STATE?
            #    continue

            if all_spawned:
                # (happens prior to shutting down at stop top time)
                # (=> earliest_unspawned is undefined)
                continue

            if int( itask.c_time ) >= int( earliest_unspawned ):
                # An EARLIER unspawned task may still spawn a successor
                # that may need me to satisfy its prerequisites.
                # The '=' here catches cotemporal unsatisfied tasks
                # (because an unsatisfied task cannot have spawned).
                continue

            if hasattr( itask, 'is_tied' ):
                # Is there a later succeeded instance of the same task?
                # It must be SUCCEEDED in case the current task fails and
                # cannot be fixed => the task's manually inserted
                # post-gap successor will need to be satisfied by said
                # succeeded task. 
                there_is = False
                for t in self.cycling_tasks:
                    if t.name == itask.name and \
                            int( t.c_time ) > int( itask.c_time ) and \
                            t.state.is_succeeded():
                                there_is = True
                                break
                if not there_is:
                    continue

            # and, by a process of elimination
            spent.append( itask )
 
        # delete the spent quick death tasks
        for itask in spent:
            self.trash( itask, 'quick' )

    def cleanup_generic( self, failed_rt ):
        # B/ THE GENERAL CASE
        # No succeeded-and-spawned task that is later than the *EARLIEST
        # UNSATISFIED* task can be deleted yet because it may still be
        # needed to satisfy new tasks that may appear when earlier (but
        # currently unsatisfied) tasks spawn. Therefore only
        # succeeded-and-spawned tasks that are earlier than the
        # earliest unsatisfied task are candidates for deletion. Of
        # these, we can delete a task only IF another spent instance of
        # it exists at a later time (but still earlier than the earliest
        # unsatisfied task) 

        # BUT while the above paragraph is correct, the method can fail
        # at restart: just before shutdown, when all running tasks have
        # finished, we briefly have 'all tasks satisfied', which allows 
        # deletion without the 'earliest unsatisfied' limit, and can
        # result in deletion of succeeded tasks that are still required
        # to satisfy others after a restart.

        # THEREFORE the correct deletion cutoff is the earlier of:
        # *EARLIEST UNSUCCEEDED*  OR *EARLIEST UNSPAWNED*, the latter
        # being required to account for sequential (and potentially
        # tied) tasks that can spawn only after finishing - thus there
        # may be tasks in the system that have succeeded but have not yet
        # spawned a successor that could still depend on the deletion
        # candidate.  The only way to use 'earliest unsatisfied'
        # over a suite restart would be to record the state of all
        # prerequisites for each task in the state dump (which may be a
        # good thing to do, eventually!)

        [ all_succeeded, earliest_unsucceeded ] = self.earliest_unsucceeded()
        if all_succeeded:
            self.log.debug( "all tasks succeeded" )
        else:
            self.log.debug( "earliest unsucceeded: " + earliest_unsucceeded )

        # time of the earliest unspawned task
        [all_spawned, earliest_unspawned] = self.earliest_unspawned()
        if all_spawned:
            self.log.debug( "all tasks spawned")
        else:
            self.log.debug( "earliest unspawned task at: " + earliest_unspawned )

        cutoff = int( earliest_unsucceeded )
        if int( earliest_unspawned ) < cutoff:
            cutoff = int( earliest_unspawned )
        self.log.debug( "cleanup cutoff: " + str(cutoff) )

        # find candidates for deletion
        candidates = {}
        for itask in self.cycling_tasks:
            if not itask.done():
                continue
            #if itask.c_time in failed_rt.keys():
            #    continue
            if int( itask.c_time ) >= cutoff:
                continue
            
            if itask.c_time in candidates.keys():
                candidates[ itask.c_time ].append( itask )
            else:
                candidates[ itask.c_time ] = [ itask ]

        # searching from newest tasks to oldest, after the earliest
        # unsatisfied task, find any done task types that appear more
        # than once - the second or later occurrences can be deleted.
        ctimes = candidates.keys()
        ctimes.sort( key = int, reverse = True )
        seen = {}
        spent = []
        for rt in ctimes:
            if int( rt ) >= cutoff:
                continue
            
            for itask in candidates[ rt ]:
                if hasattr( itask, 'is_oneoff' ):
                    # one off candidates that do not nominate a follow-on can
                    # be assumed to have no non-cotemporal dependants
                    # and can thus be eliminated.
                    try:
                        name = itask.oneoff_follow_on
                    except AttributeError:
                        spent.append( itask )
                        continue
                else:
                    name = itask.name

                if name in seen.keys():
                    # already seen this guy, so he's spent
                    spent.append( itask )
                else:
                    # first occurence
                    seen[ name ] = True
            
        # now delete the spent tasks
        for itask in spent:
            self.trash( itask, 'general' )

    def reset_task_state( self, task_id, state ):
        if state not in [ 'ready', 'waiting', 'succeeded', 'failed', 'held' ]:
            raise TaskStateError, 'Illegal reset state: ' + state
        # find the task to reset
        found = False
        for itask in self.cycling_tasks + self.asynchronous_tasks:
            if itask.id == task_id:
                found = True
                break
        if not found:
            raise TaskNotFoundError, "Task not present in suite: " + task_id

        itask.log( 'WARNING', "resetting to " + state + " state" )

        # dump state
        self.log.warning( 'pre-reset state dump: ' + self.dump_state( new_file = True ))

        if state == 'ready':
            itask.reset_state_ready()
        elif state == 'waiting':
            itask.reset_state_waiting()
        elif state == 'succeeded':
            itask.reset_state_succeeded()
        elif state == 'failed':
            itask.reset_state_failed()
        elif state == 'held':
            itask.reset_state_held()

        if state != 'failed':
            # remove the tasks's "failed" output
            itask.outputs.remove( task_id + ' failed', fail_silently=True )

    def add_prerequisite( self, task_id, message ):
        # find the task to reset
        found = False
        for itask in self.cycling_tasks + self.asynchronous_tasks:
            if itask.id == task_id:
                found = True
                break
        if not found:
            raise TaskNotFoundError, "Task not present in suite: " + task_id

        pp = plain_prerequisites( task_id ) 
        pp.add( message )

        itask.prerequisites.add_requisites(pp)

    def insertion( self, ins_id, stop_c_time=None ):
        # TO DO: UPDATE FOR ASYCHRONOUS TASKS

        # for remote insertion of a new task, or task group
        ( ins_name, ins_ctime ) = ins_id.split( '%' )

        self.log.info( "Servicing task insertion request" )

        #### TASK INSERTION GROUPS TEMPORARILY DISABLED
        ###if ins_name in ( self.config[ 'task insertion groups' ] ):
        ###    self.log.info( "Servicing group insertion request" )
        ###    ids = []
        ###    for name in self.config[ 'task insertion groups' ][ins_name]:
        ###        ids.append( name + '%' + ins_ctime )
        ###else:
        ids = [ ins_id ]

        rejected = []
        inserted = []
        to_insert = []
        for task_id in ids:
            [ name, c_time ] = task_id.split( '%' )
            # Instantiate the task proxy object
            gotit = False
            try:
                itask = self.config.get_task_proxy( name, c_time, 'waiting', stop_c_time, startup=False )
            except KeyError, x:
                try:
                    itask = self.config.get_task_proxy_raw( name, c_time, 'waiting', stop_c_time, startup=False )
                except SuiteConfigError,x:
                    self.log.warning( str(x) )
                    rejected.append( name + '%' + c_time )
                else:
                    gotit = True
            else: 
                gotit = True

            if gotit:
                # The task cycle time can be altered during task initialization
                # so we have to create the task before checking if the task
                # already exists in the system or the stop time has been reached.
                rject = False
                for task in self.cycling_tasks:
                    if itask.id == task.id:
                        # task already in the suite
                        rject = True
                        break
                if rject:
                    rejected.append( itask.id )
                    itask.prepare_for_death()
                    del itask
                else: 
                    if self.stop_time and int( itask.tag ) > int( self.stop_time ):
                        itask.log( 'WARNING', "HOLDING at configured suite stop time " + self.stop_time )
                        itask.state.set_status('held')
                    if itask.stop_c_time and int( itask.tag ) > int( itask.stop_c_time ):
                        # this task has a stop time configured, and we've reached it
                        itask.log( 'WARNING', "HOLDING at configured task stop time " + itask.stop_c_time )
                        itask.state.set_status('held')
                    inserted.append( itask.id )
                    to_insert.append(itask)

        if len( to_insert ) > 0:
            self.log.warning( 'pre-insertion state dump: ' + self.dump_state( new_file = True ))
            for task in to_insert:
                self.insert( task )
        return ( inserted, rejected )

    def purge( self, id, stop ):
        # Remove an entire dependancy tree rooted on the target task,
        # through to the given stop time (inclusive). In general this
        # involves tasks that do not even exist yet within the pool.

        # Method: trigger the target task *virtually* (i.e. without
        # running the real task) by: setting it to the succeeded state,
        # setting all of its outputs completed, and forcing it to spawn.
        # (this is equivalent to instantaneous successful completion as
        # far as cylc is concerned). Then enter the normal dependency
        # negotation process to trace the downstream effects of this,
        # also triggering subsequent tasks virtually. Each time a task
        # triggers mark it as a dependency of the target task for later
        # deletion (but not immmediate deletion because other downstream
        # tasks may still trigger off its outputs).  Downstream tasks
        # (freshly spawned or not) are not triggered if they have passed
        # the stop time, and the process is stopped is soon as a
        # dependency negotation round results in no new tasks
        # triggering.

        # Finally, reset the prerequisites of all tasks spawned during
        # the purge to unsatisfied, since they may have been satisfied
        # by the purged tasks in the "virtual" dependency negotiations.
        # TO DO: THINK ABOUT WHETHER THIS CAN APPLY TO TASKS THAT
        # ALREADY EXISTED PRE-PURGE, NOT ONLY THE JUST-SPAWNED ONES. If
        # so we should explicitly record the tasks that get satisfied
        # during the purge.

        self.log.warning( 'pre-purge state dump: ' + self.dump_state(
            new_file = True ))

        die = []
        spawn = []

        for itask in self.cycling_tasks + self.asynchronous_tasks:
            # Find the target task
            if itask.id == id:
                # set it succeeded
                itask.set_succeeded()
                # force it to spawn
                foo = self.force_spawn( itask )
                if foo:
                    spawn.append( foo )
                # mark it for later removal
                die.append( id )
                break

        # trace out the tree of dependent tasks
        something_triggered = True
        while something_triggered:
            self.negotiate()
            something_triggered = False
            for itask in self.cycling_tasks + self.asynchronous_tasks:
                if itask.ready_to_run() and int( itask.tag ) <= int( stop ):
                    something_triggered = True
                    itask.set_succeeded()
                    foo = self.force_spawn( itask )
                    if foo:
                        spawn.append( foo )
                    die.append( itask.id )
 
        # reset any prerequisites "virtually" satisfied during the purge
        for task in spawn:
            task.prerequisites.set_all_unsatisfied()

        # finally, purge all tasks marked as depending on the target
        self.kill( die, dump_state=False )

    def check_timeouts( self ):
        for itask in self.cycling_tasks + self.asynchronous_tasks:
            itask.check_timeout()

    def waiting_clocktriggered_task_ready( self ):
        # This method actually returns True if ANY task is ready to run,
        # not just clocktriggered tasks. However, this should not be a problem.
        result = False
        for itask in self.cycling_tasks + self.asynchronous_tasks:
            #print itask.id
            if itask.ready_to_run():
                result = True
                break
        return result

    def kill_cycle( self, tag ):
        # kill all tasks currently with given tag
        task_ids = []
        for itask in self.cycling_tasks + self.asynchronous_tasks:
            if itask.tag == tag: # and itask.get_status() == 'waiting':
                task_ids.append( itask.id )
        self.kill( task_ids )

    def spawn_and_die_cycle( self, tag ):
        # spawn and kill all tasks currently with given tag
        task_ids = {}
        for itask in self.cycling_tasks + self.asynchronous_tasks:
            if itask.tag == tag: # and itask.get_status() == 'waiting':
                task_ids[ itask.id ] = True
        self.spawn_and_die( task_ids )

    def spawn_and_die( self, task_ids, dump_state=True, reason='remote request' ):
        # Spawn and kill all tasks in task_ids. Works for dict or list input.
        # TO DO: clean up use of spawn_and_die (the keyword args are clumsy)

        if dump_state:
            self.log.warning( 'pre-spawn-and-die state dump: ' + self.dump_state( new_file = True ))

        for id in task_ids:
            # find the task
            found = False
            itask = None
            for t in self.cycling_tasks + self.asynchronous_tasks:
                if t.id == id:
                    found = True
                    itask = t
                    break

            if not found:
                self.log.warning( "task to kill not found: " + id )
                return

            itask.log( 'DEBUG', reason )

            if not itask.state.has_spawned():
                # forcibly spawn the task and create its successor
                itask.state.set_spawned()
                itask.log( 'DEBUG', 'forced spawning' )

                new_task = itask.spawn( 'waiting' )
 
                if self.stop_time and int( new_task.tag ) > int( self.stop_time ):
                    # we've reached the stop time
                    new_task.log( 'WARNING', 'HOLDING at configured suite stop time' )
                    new_task.state.set_status('held')
                # perpetuate the task stop time, if there is one
                new_task.stop_c_time = itask.stop_c_time
                self.insert( new_task )
            else:
                # already spawned: the successor already exists
                pass

            # now kill the task
            self.trash( itask, reason )

    def kill( self, task_ids, dump_state=True ):
        # kill without spawning all tasks in task_ids
        if dump_state:
            self.log.warning( 'pre-kill state dump: ' + self.dump_state( new_file = True ))
        for id in task_ids:
            # find the task
            found = False
            itask = None
            for t in self.cycling_tasks + self.asynchronous_tasks:
                if t.id == id:
                    found = True
                    itask = t
                    break
            if not found:
                self.log.warning( "task to kill not found: " + id )
                return
            self.trash( itask, 'by request' )

    def trash( self, task, reason ):
        # remove a task from the pool
        count = 0
        alerted = False
        while count < 10:
            # retry loop for Pyro protocol error (see below)
            count += 1
            try:
                self.pyro.disconnect( task )
            except NamingError:
                # HANDLE ATTEMPTED INSERTION OF A TASK THAT ALREADY EXISTS.
                self.log.critical( task.id + ' CANNOT BE REMOVED (no such task)' )
                # do not retry
                break
            except ProtocolError, x:
                # HANDLE MYSTERIOUS PYRO NAMESERVER PROBLEM (NIWA 11-12 SEPT 2010):
                # registering and deregistering objects from pyro-ns (and even use of 
                # 'pyro-nsc ping'!) caused occasional 'incompatible protocol version'
                # errors. Fixed by restarting pyro-ns, but cause unknown thus far.
                # PROBABLY NOT NEEDED NOW AS WE NO LONGER USE THE PYRO NAMESERVER
                self.log.critical( task.id + ' CANNOT BE REMOVED (Pyro protocol error) ' + str( count ) + '/10' )
                if not alerted:
                    alerted = True
                    print x
                    self.log.critical( 'Check your pyro installations are version compatible' )
            else:
                task.log( 'NORMAL', "removing from suite (" + reason + ")" )
                task.prepare_for_death()
                if task in self.cycling_tasks:
                    self.cycling_tasks.remove( task )
                elif task in self.asynchronous_tasks:
                    self.asynchronous_tasks.remove( task )
                del task
                # do not retry
                break

    def insert( self, task ):
        # insert a task into the pool
        count = 0
        alerted = False
        while count < 10:
            # retry loop for Pyro protocol error (see below)
            count += 1
            try:
                self.pyro.connect( task, task.id )
            except NamingError:
                # HANDLE ATTEMPTED INSERTION OF A TASK THAT ALREADY EXISTS.
                self.log.critical( task.id + ' CANNOT BE INSERTED (already exists)' )
                # do not retry
                break
            except ProtocolError, x:
                # HANDLE MYSTERIOUS PYRO NAMESERVER PROBLEM (NIWA 11-12 SEPT 2010):
                # registering and deregistering objects from pyro-ns (and even use of 
                # 'pyro-nsc ping'!) caused occasional 'incompatible protocol version'
                # errors. Fixed by restarting pyro-ns, but cause unknown thus far.
                # PROBABLY NOT NEEDED NOW AS WE NO LONGER USE THE PYRO NAMESERVER
                self.log.critical( task.id + ' CANNOT BE INSERTED (Pyro protocol error) ' + str( count ) + '/10' )
                if not alerted:
                    alerted = True
                    print x
                    self.log.critical( 'Check your pyro installations are version compatible' )
            else:
                task.log('NORMAL', "task proxy inserted" )
                if task.is_cycling():
                    self.cycling_tasks.append( task )
                else:
                    self.asynchronous_tasks.append( task )
                # do not retry
                break

    def filter_initial_task_list( self, inlist ):
        included_by_rc  = self.config['scheduling']['special tasks']['include at start-up']
        excluded_by_rc  = self.config['scheduling']['special tasks']['exclude at start-up']
        outlist = []
        for name in inlist:
            if name in excluded_by_rc:
                continue
            if len( included_by_rc ) > 0:
                if name not in included_by_rc:
                    continue
            outlist.append( name ) 
        return outlist

    def initialize_runtime_graph( self ):
        title = 'suite ' + self.suite + ' run-time dependency graph'
        # create output directory if necessary
        odir = self.config['visualization']['run time graph']['directory']
        mkdir_p( odir )
        self.runtime_graph_file = \
                os.path.join( odir, 'runtime-graph.dot' )
        self.runtime_graph = graphing.CGraph( title, self.config['visualization'] )
        self.runtime_graph_finalized = False
        self.runtime_graph_cutoff = self.config['visualization']['run time graph']['cutoff']

    def update_runtime_graph( self, task ):
        if self.runtime_graph_finalized:
            return
        # stop if all tasks are more than cutoff hours beyond suite start time
        if self.start_time:
            st = ct( self.start_time )
        else:
            st = ct( self.initial_oldest_ctime )

        ot = ct( self.get_oldest_c_time() )
        delta1 = ot.subtract( st )
        delta2 = datetime.timedelta( 0, 0, 0, 0, 0, self.runtime_graph_cutoff, 0 )
        if delta1 >= delta2:
            self.finalize_runtime_graph()
            return
        # ignore task if its ctime more than configured hrs beyond suite start time?
        st = st
        tt = ct( task.c_time )
        delta1 = tt.subtract(st)
        if delta1 >= delta2:
            return
        for id in task.get_resolved_dependencies():
            l = id
            r = task.id 
            self.runtime_graph.add_edge( l,r )
            self.write_runtime_graph()

    def update_runtime_graph_async( self, task ):
        if self.runtime_graph_finalized:
            return
        # stop if all tasks are beyond the first tag
        ot = self.get_oldest_async_tag()
        if ot > 1:
            self.finalize_runtime_graph()
            return
        # ignore tasks beyond the first tag 
        tt = int( task.tag )
        if tt > 1:
            return
        for id in task.get_resolved_dependencies():
            l = id
            r = task.id 
            self.runtime_graph.add_edge( l,r )
            self.write_runtime_graph()

    def write_runtime_graph( self ):
        #print "Writing graph", self.runtime_graph_file
        self.runtime_graph.write( self.runtime_graph_file )

    def finalize_runtime_graph( self ):
        #if self.runtime_graph_finalized:
        #    return
        #print "Finalizing graph", self.runtime_graph_file
        self.write_runtime_graph()
        self.runtime_graph_finalized = True

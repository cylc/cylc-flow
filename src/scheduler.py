#!/usr/bin/env python

##### TO DO: self.config.check_task_groups() #####

import task
import socket
import logging
import datetime
import port_scan
import cycle_time
import pygraphviz
#import dead_letter
import pimp_my_logger
import accelerated_clock 
import re, os, sys, shutil
from execute import execute
from rolling_archive import rolling_archive
from cylc_pyro_server import pyro_server
from state_summary import state_summary
from remote_switch import remote_switch
from OrderedDict import OrderedDict
from job_submit import job_submit
from lockserver import lockserver
from suite_lock import suite_lock
from suite_id import identifier
from mkdir_p import mkdir_p
from config import config 
from broker import broker
from Pyro.errors import NamingError, ProtocolError

class scheduler(object):
    def __init__( self ):
        # PROVIDE IN DERIVED CLASSES:
        # 1/ self.parser = OptionParser( usage )
        # 2/ load_tasks()

        # SUITE OWNER
        self.owner = os.environ['USER']

        # SUITE HOST
        self.host= socket.getfqdn()

        # STARTUP BANNER
        self.banner = {}

        # TASK POOL
        self.tasks = []

        # DEPENDENCY BROKER
        self.broker = broker()

        # COMMANDLINE OPTIONS
        self.parser.set_defaults( dummy_mode=False, practice_mode=False,
                include=None, exclude=None, debug=False )

        self.parser.add_option( "--until", 
                help="Shut down after all tasks have PASSED this cycle time.",
                metavar="CYCLE", action="store", dest="stop_time" )

        self.parser.add_option( "--pause",
                help="Refrain from running tasks AFTER this cycle time.",
                metavar="CYCLE", action="store", dest="pause_time" )

        self.parser.add_option( "--exclude",
                help="Comma-separated list of tasks to exclude at startup "
                "(this can also be done via the suite.rc file).",
                metavar="LIST", action="store", dest='exclude' )

        self.parser.add_option( "--include",
                help="Comma-separated list of tasks to include at startup "
                "(all other tasks will be excluded).",
                metavar="LIST", action="store", dest='include' )

        self.parser.add_option( "-d", "--dummy-mode",
                help="Run the suite in simulation mode: each task is replaced "
                "by 'cylc-wrapper bin/true', and the wall clock is accelerated.",
                action="store_true", dest="dummy_mode" )

        self.parser.add_option( "-p", "--practice-mode",
                help="Clone an existing suite in dummy mode using new state "
                "and logging directories to avoid corrupting the original. "
                "Failed tasks will not be reset to waiting in the clone.",
                action="store_true", dest="practice_mode" )

        self.parser.add_option( "--failout", help=\
                "(DUMMY MODE) get task NAME at cycle time CYCLE to report failure "
                "and then abort. Use this to test failure and recovery scenarios.",
                metavar="NAME%CYCLE", action="store", dest="failout_task_id" )

        self.parser.add_option( "--debug", help=\
                "Turn on the 'debug' logging level and print the Python "
                "source traceback for unhandled exceptions (otherwise "
                "just the error message will be printed).",
                action="store_true", dest="debug" )

        self.parser.add_option( "--timing", help=\
                "Turn on main task processing loop timing, which may be useful "
                "for testing very large suites of 1000+ tasks.",
                action="store_true", default=False, dest="timing" )

        self.parse_commandline()
        self.check_not_running_already()
        self.configure_suite()
        self.print_banner()
        # LOAD TASK POOL ACCORDING TO STARTUP METHOD (PROVIDED IN DERIVED CLASSES) 
        self.load_tasks()

    def parse_commandline( self ):
        # SUITE NAME
        self.suite = self.args[0]

        # MODE OF OPERATION (REAL, DUMMY, practice)
        if self.options.dummy_mode and self.options.practice_mode:
            parser.error( "Choose ONE of dummy or practice mode")
        if self.options.dummy_mode:
            self.banner['Mode of operation'] = 'DUMMY'
            self.dummy_mode = True
            self.practice = False
        elif self.options.practice_mode:
            self.banner['Mode of operation'] = 'DUMMY (PRACTICE)'
            self.dummy_mode = True
            self.practice = True
        else:
            self.banner['Mode of operation'] = 'REAL'
            self.dummy_mode = False
            self.practice = False

        # LOGGING LEVEL
        if self.options.debug:
            self.logging_level = logging.DEBUG
        else:
            self.logging_level = logging.INFO

        # LIST OF TASKS TO INCLUDE AT STARTUP (EXCLUDING OTHERS)
        self.include_via_cline = []
        if self.options.include:
            self.include_via_cline = self.options.include.split(',')

        # LIST OF TASKS TO EXCLUDE AT STARTUP
        self.exclude_via_cline = []
        if self.options.exclude:
            self.exclude_via_cline = self.options.exclude.split(',')

    def check_not_running_already( self ):
        # CHECK SUITE IS NOT ALREADY RUNNING (unless practice mode)
        try:
            port = port_scan.get_port( self.suite, self.owner, self.host )
        except port_scan.SuiteNotFoundError,x:
            # Suite Not Found: good - it's not running already!
            pass
        else:
            if self.options.practice_mode:
                print "Continuing in Cylc Practice Mode"
            else:
                raise SystemExit( "ERROR: suite " + self.suite + " is already running")


    def configure_suite( self ):
        # LOAD SUITE CONFIG FILE
        self.config = config( self.suite, dummy_mode=self.dummy_mode )
        self.config.create_directories()

        self.suite_dir = self.config.get_dirname()

        # DETERMINE SUITE LOGGING AND STATE DUMP DIRECTORIES
        self.logging_dir = os.path.join( self.config['top level logging directory'],    self.suite ) 
        self.state_dump_dir   = os.path.join( self.config['top level state dump directory'], self.suite )
        if self.practice:
            self.logging_dir += '-practice'
            self.state_dump_dir   += '-practice'
        # create logging and state dump directoriesif necessary
        mkdir_p( self.logging_dir )
        mkdir_p( self.state_dump_dir )

        self.banner[ 'Logging to' ] = self.logging_dir
        self.banner[ 'State dump' ] = self.state_dump_dir
        # state dump file
        self.state_dump_filename = os.path.join( self.state_dump_dir, 'state' )

        # STOP TIME?
        self.stop_time = None
        if self.options.stop_time:
            self.stop_time = self.options.stop_time
            if not cycle_time.is_valid( self.stop_time ):
                self.parser.error( "invalid cycle time: " + self.stop_time )
            self.banner[ 'Stopping at' ] = self.stop_time

        # PAUSE TIME?
        self.suite_hold_now = False
        self.pause_time = None
        if self.options.pause_time:
            self.pause_time = self.options.pause_time
            if not cycle_time.is_valid( self.pause_time ):
                self.parser.error( "invalid cycle time: " + self.pause_time )
            self.banner[ 'Pausing at' ] = self.pause_time

        # CONFIGURE SUITE PYRO SERVER
        if self.practice:
            # modify suite name so we can run next to the original suite.
            suitename = self.suite + "-practice"
        else:
            suitename = self.suite
        self.pyro = pyro_server( suitename, use_passphrase=self.config['use secure passphrase'] )
        self.port = self.pyro.get_port()
        self.banner[ 'Listening on port' ] = self.port

        # REMOTELY ACCESSIBLE SUITE IDENTIFIER
        suite_id = identifier( self.suite, self.owner )
        self.pyro.connect( suite_id, 'cylcid', qualified = False )

        # REMOTELY ACCESSIBLE SUITE STATE SUMMARY
        self.suite_state = state_summary( self.config, self.dummy_mode )
        self.pyro.connect( self.suite_state, 'state_summary')

        # REMOTELY ACCESSIBLE DEAD LETTER BOX
        # --- NO LONGER USED ---
        #self.dead_letter_box = dead_letter.letter_box()
        #self.pyro.connect( self.dead_letter_box, 'dead_letter_box')

        # USE QUICK TASK ELIMINATION?
        self.use_quick = self.config['use quick task elimination'] 

        # USE LOCKSERVER?
        self.use_lockserver = self.config['use lockserver']
        if self.dummy_mode:
            # no need for lockserver in dummy mode
            self.use_lockserver = False

        if self.use_lockserver:
            # check that user is running a lockserver
            self.lockserver_port = lockserver( self.owner, self.host ).ping()

        # ALLOW MULTIPLE SIMULTANEOUS INSTANCES?
        self.exclusive_suite_lock = not self.config[ 'allow multiple simultaneous suite instances' ]

        # TASK EVENT HOOKS
        task.task_submitted_hook = self.config['task submitted hook']
        task.task_started_hook = self.config['task started hook']
        task.task_finished_hook = self.config['task finished hook']
        task.task_failed_hook = self.config['task failed hook']
        task.task_warning_hook = self.config['task warning hook']
        task.task_submission_failed_hook = self.config['task submission failed hook']
        task.task_timeout_hook = self.config['task timeout hook']
        task.task_submission_timeout_minutes = self.config['task submission timeout minutes']

        # CYLC EXECUTION ENVIRONMENT
        cylcenv = OrderedDict()
        cylcenv[ 'CYLC_MODE' ] = 'scheduler'
        cylcenv[ 'CYLC_SUITE_HOST' ] =  str( self.host )
        cylcenv[ 'CYLC_SUITE_PORT' ] =  self.pyro.get_port()
        cylcenv[ 'CYLC_DIR' ] = os.environ[ 'CYLC_DIR' ]
        cylcenv[ 'CYLC_SUITE_DIR' ] = self.suite_dir
        cylcenv[ 'CYLC_SUITE_NAME' ] = self.suite
        cylcenv[ 'CYLC_SUITE_OWNER' ] = self.owner
        cylcenv[ 'CYLC_USE_LOCKSERVER' ] = str( self.use_lockserver )

        # USER DEFINED GLOBAL ENVIRONMENT
        globalenv = OrderedDict()
        for var in self.config['environment']:
            globalenv[ var ] = self.config['environment'][var]

        # CLOCK (accelerated time in dummy mode)
        rate = self.config['dummy mode']['clock rate in seconds per dummy hour']
        offset = self.config['dummy mode']['clock offset from initial cycle time in hours']
        self.clock = accelerated_clock.clock( int(rate), int(offset), self.dummy_mode ) 
        self.pyro.connect( self.clock, 'clock' )

        self.failout_task_id = self.options.failout_task_id
        cylcenv['CYLC_DUMMY_SLEEP'] =  self.config['dummy mode']['task run time in seconds']

        # JOB SUBMISSION
        job_submit.dummy_mode = self.dummy_mode
        job_submit.cylc_env = cylcenv
        job_submit.global_env = globalenv
        job_submit.joblog_dir = self.config[ 'job submission log directory' ]
        job_submit.dummy_command = self.config['dummy mode'][ 'command' ]
        job_submit.dummy_command_fail = self.config['dummy mode'][ 'command fail' ]
        if self.dummy_mode and self.failout_task_id:
            job_submit.failout_id = self.failout_task_id

        # LOCAL ENVIRONMENT
        # Access to the suite bin directory required for direct job
        # submission methods (background, at_now). *Prepend* suite bin
        # to $PATH in case this is a subsuite (the parent and sub suites
        # may have task scripts with common names - NOTE that this is 
        # still somewhat dangerous: if a subsuite task script is,
        # erroneously, not executable, one in the parent suite, if it
        # exists, will be, erroneously, invoked instead).
        os.environ['PATH'] = self.suite_dir + '/bin:' + os.environ['PATH'] 

        # LIST OF ALL TASK NAMES
        self.task_name_list = self.config.get_task_name_list()

        # PIMP THE SUITE LOG
        self.log = logging.getLogger( 'main' )
        pimp_my_logger.pimp_it( \
             self.log, self.logging_dir, \
                self.logging_level, self.dummy_mode, self.clock )

        # STATE DUMP ROLLING ARCHIVE
        arclen = self.config[ 'number of state dump backups' ]
        self.state_dump_archive = rolling_archive( self.state_dump_filename, arclen )

        # REMOTE CONTROL INTERFACE
        # TO DO: DO WE NEED TO LOAD TASK LIST FIRST?
        # TO DO: THIS IS CLUNKY - PASSING IN SELF TO GIVE ACCESS TO TASK
        # POOL METHODS.
        self.remote = remote_switch( self.config, self.clock, self.suite_dir, self.owner, self, self.failout_task_id )
        self.pyro.connect( self.remote, 'remote' )

    def print_banner( self ):
        print "_______________________________________________"
        print "_ Cylc Self Organising Adaptive Metascheduler _"
        print "_\    (c) Hilary Oliver, NIWA, 2008-2011     /_"
        print "__\        cylc is pronounced 'silk'        /__"
        print "___\________________C_Y_L_C________________/___"
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
           backup = self.state_dump_filename + '.' + datetime.datetime.now().isoformat()
           print "Backing up the state dump file:"
           print "  " + self.state_dump_filename + " --> " + backup
           try:
               shutil.copyfile( self.state_dump_filename, backup )
           except:
               raise SystemExit( "ERROR: State dump file copy failed" )

    def run( self ):
        if self.use_lockserver:
            if self.practice:
                suitename = self.suite + '-practice'
            else:
                suitename = self.suite

            # request suite access from the lock server
            if suite_lock( suitename, self.suite_dir, self.owner, self.host, self.lockserver_port, 'scheduler' ).request_suite_access( self.exclusive_suite_lock ):
               self.lock_acquired = True
            else:
               raise SystemExit( "Failed to acquire a suite lock" )

        if not self.practice:
            self.back_up_statedump_file()

        if self.pause_time:
            # TO DO: HANDLE STOP AND PAUSE TIMES THE SAME WAY?
            self.set_suite_hold( self.pause_time )

        print "\nSTARTING\n"

        while True: # MAIN LOOP

            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.

            if self.process_tasks():
                #print "ENTERING MAIN LOOP"
                if self.options.timing:
                    main_loop_start_time = datetime.datetime.now()

                self.negotiate()
                self.run_tasks()
                self.cleanup()
                self.spawn()
                self.dump_state()

                self.suite_state.update( self.tasks, self.clock, \
                        self.paused(), self.will_pause_at(), \
                        self.remote.halt, self.will_stop_at() )

                if self.options.timing:
                    delta = datetime.datetime.now() - main_loop_start_time
                    seconds = delta.seconds + float(delta.microseconds)/10**6
                    print "MAIN LOOP TIME TAKEN:", seconds, "seconds"

            if self.all_tasks_finished():
                self.log.critical( "ALL TASKS FINISHED" )
                break

            if self.remote.halt_now or self.remote.halt and self.no_tasks_running():
                self.log.critical( "ALL RUNNING TASKS FINISHED" )
                break

            self.check_timeouts(self.clock.get_datetime())

            # REMOTE METHOD HANDLING; with no timeout and single- threaded pyro,
            # handleRequests() returns after one or more remote method
            # invocations are processed (these are not just task messages, hence
            # the use of the state_changed variable above).
            # HOWEVER, we now need to check if contact tasks are ready
            # to trigger according on wall clock time, so we also need a
            # timeout to handle this when nothing else is happening.
            #--

            # incoming task messages set task.state_changed to True
            self.pyro.handleRequests(timeout=1)
        # END MAIN LOOP

        self.shutdown()

    def process_tasks( self ):
        # do we need to do a pass through the main task processing loop?
        answer = False
        if task.state_changed:
            # cause one pass through the main loop
            answer = True
            # reset task.state_changed
            task.state_changed = False
            
        if self.remote.process_tasks:
            # cause one pass through the main loop
            answer = True
            # reset the remote control flag
            self.remote.process_tasks = False
            
        if self.waiting_contact_task_ready( self.clock.get_datetime() ):
            # This method actually returns True if ANY task is ready to run,
            # not just contact tasks. However, this should not be a problem.
            # For a contact task, this means the contact time is up AND
            # any prerequisites are satisfied, so it can't result in
            # multiple passes through the main loop.

            # cause one pass through the main loop
            answer = True

        return answer

    def shutdown( self ):
        print "\nSTOPPING"

        if self.pyro:
            self.pyro.shutdown()

        if self.use_lockserver:
            # do this last
            if self.practice:
                suitename = self.suite + '-practice'
            else:
                suitename = self.suite

            if self.lock_acquired:
                print "Releasing suite lock"
                lock = suite_lock( suitename, self.suite_dir, self.owner, self.host, self.lockserver_port, 'scheduler' )
                if not lock.release_suite_access():
                    print >> sys.stderr, 'failed to release suite!'


    def get_tasks( self ):
        return self.tasks

    def set_stop_time( self, stop_time ):
        self.log.debug( "Setting stop time: " + stop_time )
        self.stop_time = stop_time

    def set_suite_hold( self, ctime = None ):
        self.log.warning( 'pre-hold state dump: ' + self.dump_state( new_file = True ))
        if ctime:
            self.pause_time = ctime
            self.log.critical( "HOLD: no new tasks will run from " + ctime )
        else:
            self.suite_hold_now = True
            self.log.critical( "HOLD: no more tasks will run")

    def unset_suite_hold( self ):
        if self.suite_hold_now:
            self.log.critical( "UNHOLD: new tasks will run when ready")
            self.suite_hold_now = False
            self.pause_time = None
        if self.stop_time:
            self.log.critical( "UNSTOP: unsetting suite stop time")
            self.stop_time = None

    def will_stop_at( self ):
        return self.stop_time

    def paused( self ):
        return self.suite_hold_now

    def stopping( self ):
        if self.stop_time:
            return True
        else:
            return False

    def will_pause_at( self ):
        return self.pause_time

    def get_oldest_c_time( self ):
        # return the cycle time of the oldest task
        oldest = 9999887766
        for itask in self.tasks:
            #if itask.state.is_failed():  # uncomment for earliest NON-FAILED 
            #    continue

            # avoid daemon tasks
            if hasattr( itask, 'daemon_task' ):
                continue

            if int( itask.c_time ) < int( oldest ):
                oldest = itask.c_time
        return oldest

    def no_tasks_running( self ):
        # return True if no tasks are submitted or running
        #--
        for itask in self.tasks:
            if itask.state.is_running() or itask.state.is_submitted():
                return False
        return True

    def all_tasks_finished( self ):
        # return True if all tasks have finished AND spawned
        #--
        for itask in self.tasks:
            if not itask.state.is_finished() or not itask.state.has_spawned():
                return False
        return True


    def negotiate( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        # BROKERED NEGOTIATION is O(n) in number of tasks.
        #--

        self.broker.reset()

        for itask in self.tasks:
            # register task outputs
            self.broker.register( itask )

        for itask in self.tasks:
            # try to satisfy me (itask) if I'm not already satisfied.
            if itask.not_fully_satisfied():
                self.broker.negotiate( itask )

        for itask in self.tasks:
            itask.check_requisites()

    def run_tasks( self ):
        # tell each task to run if it is ready
        # unless the suite is on hold
        #--
        if self.suite_hold_now:
            # general suite hold
            self.log.debug( 'not asking any tasks to run (general suite hold in place)' )
            return

        for itask in self.tasks:
                if self.pause_time:
                    if int( itask.c_time ) > int( self.pause_time ):
                        self.log.debug( 'not asking ' + itask.id + ' to run (' + self.pause_time + ' hold in place)' )
                        continue

                current_time = self.clock.get_datetime()
                itask.run_if_ready( current_time )

    def spawn( self ):
        # create new tasks foo(T+1) if foo has not got too far ahead of
        # the slowest task, and if foo(T) spawns
        #--

        # update oldest suite cycle time
        oldest_c_time = self.get_oldest_c_time()

        for itask in self.tasks:

            tdiff = cycle_time.decrement( itask.c_time, self.config['maximum runahead hours'])
            if int( tdiff ) > int( oldest_c_time ):
                # too far ahead: don't spawn this task.
                itask.log( 'DEBUG', "delaying spawning (too far ahead)" )
                continue

            if itask.ready_to_spawn():
                itask.log( 'DEBUG', 'spawning')

                # dynamic task object creation by task and module name
                new_task = itask.spawn( 'waiting' )
                if self.stop_time and int( new_task.c_time ) > int( self.stop_time ):
                    # we've reached the stop time: delete the new task 
                    new_task.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
                    new_task.prepare_for_death()
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
                    self.insert( new_task )


    def force_spawn( self, itask ):
        if itask.state.has_spawned():
            return None
        else:
            itask.state.set_spawned()
            itask.log( 'DEBUG', 'forced spawning')
            # dynamic task object creation by task and module name
            new_task = itask.spawn( 'waiting' )
            if self.stop_time and int( new_task.c_time ) > int( self.stop_time ):
                # we've reached the stop time: delete the new task 
                new_task.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
                new_task.prepare_for_death()
                del new_task
            else:
                # no stop time, or we haven't reached it yet.
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
        if self.dummy_mode:
            FILE.write( 'dummy time : ' + self.clock.dump_to_str() + ',' + str( self.clock.get_rate()) + '\n' )
        else:
            FILE.write( 'suite time : ' + self.clock.dump_to_str() + '\n' )

        # FOR OLD STATIC TASK CLASS DEFS:
        ####for name in self.task_name_list:
        ####    mod = __import__( 'task_classes' )
        ####    cls = getattr( mod, name )
        ####    cls.dump_class_vars( FILE )

        # FOR NEW DYNAMIC TASK CLASS DEFS:
        for itask in self.tasks:
            # TO DO: CHECK THIS STILL WORKS 
            itask.dump_class_vars( FILE )
             
        # task instance variables
        for itask in self.tasks:
            itask.dump_state( FILE )
        FILE.close()
        # return the filename (minus path)
        return os.path.basename( filename )

    def earliest_unspawned( self ):
        all_spawned = True
        earliest_unspawned = '9999887766'
        for itask in self.tasks:
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
        for itask in self.tasks:
            if not itask.prerequisites.all_satisfied():
                all_satisfied = False
                if not earliest_unsatisfied:
                    earliest_unsatisfied = itask.c_time
                elif int( itask.c_time ) < int( earliest_unsatisfied ):
                    earliest_unsatisfied = itask.c_time

        return [ all_satisfied, earliest_unsatisfied ]

    def earliest_unfinished( self ):
        # find the earliest unfinished task
        all_finished = True
        earliest_unfinished = '9999887766'
        for itask in self.tasks:
            #if itask.state.is_failed():  # uncomment for earliest NON-FAILED
            #    continue

            # avoid daemon tasks
            if hasattr( itask, 'daemon_task' ):
                continue

            if not itask.state.is_finished():
                all_finished = False
                if not earliest_unfinished:
                    earliest_unfinished = itask.c_time
                elif int( itask.c_time ) < int( earliest_unfinished ):
                    earliest_unfinished = itask.c_time

        return [ all_finished, earliest_unfinished ]

    def cleanup( self ):
        # Delete tasks that are no longer needed, i.e. those that
        # spawned, finished, AND are no longer needed to satisfy
        # the prerequisites of other tasks.
        #--

        # times of any failed tasks. 
        failed_rt = {}
        for itask in self.tasks:
            if itask.state.is_failed():
                failed_rt[ itask.c_time ] = True

        # suicide
        for itask in self.tasks:
            if itask.suicide_prerequisites.count() != 0:
                if itask.suicide_prerequisites.all_satisfied():
                    self.spawn_and_die( [itask.id], dump_state=False, reason='death by suicide' )

        #### RESTORE FOR TESTING ASYNCHRONOUS TASK FUNCTIONALITY:
        #### self.cleanup_async()

        if self.use_quick:
            self.cleanup_non_intercycle( failed_rt )

        self.cleanup_generic( failed_rt )

    def cleanup_async( self ):
        spent = []
        for itask in self.tasks:
            if not itask.done():
                continue
            try:
                itask.death_prerequisites
            except AttributeError:
                pass
            else:
                if itask.death_prerequisites.all_satisfied():
                    print "ASYNC SPENT", itask.id
                    spent.append( itask )

        # delete the spent tasks
        for itask in spent:
            self.trash( itask, 'quick death' )

    def cleanup_non_intercycle( self, failed_rt ):
        # A/ Non INTERCYCLE tasks by definition have ONLY COTEMPORAL
        # DOWNSTREAM DEPENDANTS). i.e. they are no longer needed once
        # their cotemporal peers have finished AND there are no
        # unspawned tasks with earlier cycle times. So:
        #
        # (i) FREE TASKS are spent if they are:
        #    spawned, finished, no earlier unspawned tasks.
        #
        # (ii) TIED TASKS are spent if they are:
        #    spawned, finished, no earlier unspawned tasks, AND there is
        #    at least one subsequent instance that is FINISHED
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
        for itask in self.tasks:
            if itask.intercycle: 
                # task not up for consideration here
                continue
            if not itask.has_spawned():
                # task has not spawned yet, or will never spawn (oneoff tasks)
                continue
            if not itask.done():
                # task has not finished yet
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
                # Is there a later finished instance of the same task?
                # It must be FINISHED in case the current task fails and
                # cannot be fixed => the task's manually inserted
                # post-gap successor will need to be satisfied by said
                # finished task. 
                there_is = False
                for t in self.tasks:
                    if t.name == itask.name and \
                            int( t.c_time ) > int( itask.c_time ) and \
                            t.state.is_finished():
                                there_is = True
                                break
                if not there_is:
                    continue

            # and, by a process of elimination
            spent.append( itask )
 
        # delete the spent quick death tasks
        for itask in spent:
            self.trash( itask, 'quick death' )

    def cleanup_generic( self, failed_rt ):
        # B/ THE GENERAL CASE
        # No finished-and-spawned task that is later than the *EARLIEST
        # UNSATISFIED* task can be deleted yet because it may still be
        # needed to satisfy new tasks that may appear when earlier (but
        # currently unsatisfied) tasks spawn. Therefore only
        # finished-and-spawned tasks that are earlier than the
        # earliest unsatisfied task are candidates for deletion. Of
        # these, we can delete a task only IF another spent instance of
        # it exists at a later time (but still earlier than the earliest
        # unsatisfied task) 

        # BUT while the above paragraph is correct, the method can fail
        # at restart: just before shutdown, when all running tasks have
        # finished, we briefly have 'all tasks satisfied', which allows 
        # deletion without the 'earliest unsatisfied' limit, and can
        # result in deletion of finished tasks that are still required
        # to satisfy others after a restart.

        # THEREFORE the correct deletion cutoff is the earlier of:
        # *EARLIEST UNFINISHED*  OR *EARLIEST UNSPAWNED*, the latter
        # being required to account for sequential (and potentially
        # tied) tasks that can spawn only after finishing - thus there
        # may be tasks in the system that have finished but have not yet
        # spawned a successor that could still depend on the deletion
        # candidate.  The only way to use 'earliest unsatisfied'
        # over a suite restart would be to record the state of all
        # prerequisites for each task in the state dump (which may be a
        # good thing to do, eventually!)

        [ all_finished, earliest_unfinished ] = self.earliest_unfinished()
        if all_finished:
            self.log.debug( "all tasks finished" )
        else:
            self.log.debug( "earliest unfinished: " + earliest_unfinished )

        # time of the earliest unspawned task
        [all_spawned, earliest_unspawned] = self.earliest_unspawned()
        if all_spawned:
            self.log.debug( "all tasks spawned")
        else:
            self.log.debug( "earliest unspawned task at: " + earliest_unspawned )

        cutoff = int( earliest_unfinished )
        if int( earliest_unspawned ) < cutoff:
            cutoff = int( earliest_unspawned )
        self.log.debug( "cleanup cutoff: " + str(cutoff) )

        # find candidates for deletion
        candidates = {}
        for itask in self.tasks:
            if not itask.done():
                continue
            if itask.c_time in failed_rt.keys():
                continue
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
                    # oneoff candidates that do not nominate a follow-on can
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


    def reset_task( self, task_id ):
        self.log.warning( 'pre-reset state dump: ' + self.dump_state( new_file = True ))
        found = False
        for itask in self.tasks:
            if itask.id == task_id:
                found = True
                break

        if found:
            itask.log( 'WARNING', "resetting to waiting state" )
            itask.state.set_status( 'waiting' )
            itask.prerequisites.set_all_unsatisfied()
            itask.outputs.set_all_incomplete()
            try:
                # remove the tasks's "failed" output
                itask.outputs.remove( task_id + ' failed' )
            except:
                # task had no "failed" output
                pass
        else:
            self.log.warning( "task to reset not found: " + task_id )

    def reset_task_to_ready( self, task_id ):
        self.log.warning( 'pre-reset state dump: ' + self.dump_state( new_file = True ))
        found = False
        for itask in self.tasks:
            if itask.id == task_id:
                found = True
                break

        if found:
            itask.log( 'WARNING', "resetting to ready state" )
            itask.state.set_status( 'waiting' )
            itask.prerequisites.set_all_satisfied()
            itask.outputs.set_all_incomplete()
            try:
                # remove the tasks's "failed" output
                itask.outputs.remove( task_id + ' failed' )
            except:
                # task had no "failed" output
                pass
        else:
            self.log.warning( "task to reset not found: " + task_id )

    def reset_task_to_finished( self, task_id ):
        self.log.warning( 'pre-reset state dump: ' + self.dump_state( new_file = True ))
        found = False
        for itask in self.tasks:
            if itask.id == task_id:
                found = True
                break

        if found:
            itask.log( 'WARNING', "resetting to finished state" )
            itask.state.set_status( 'finished' )
            itask.prerequisites.set_all_satisfied()
            itask.outputs.set_all_complete()
            try:
                # remove the tasks's "failed" output
                itask.outputs.remove( task_id + ' failed' )
            except:
                # task had no "failed" output
                pass
        else:
            self.log.warning( "task to reset not found: " + task_id )

    def insertion( self, ins_id ):
        # for remote insertion of a new task, or task group
        self.log.warning( 'pre-insertion state dump: ' + self.dump_state( new_file = True ))
        try:
            ( ins_name, ins_ctime ) = ins_id.split( '%' )
            print
            if ins_name in self.task_name_list:
                print "INSERTING A TASK"
                ids = [ ins_id ]
            elif ins_name in ( self.config[ 'task insertion groups' ] ).keys():
                print "INSERTING A GROUP OF TASKS"
                tasknames = self.config[ 'task insertion groups' ][ins_name]
                ids = []
                for name in tasknames:
                    ids.append( name + '%' + ins_ctime )
            else:
                # THIS WILL BE CAUGHT BY THE TRY BLOCK
                raise SystemExit("no such task or group")

            for task_id in ids:
                [ name, c_time ] = task_id.split( '%' )
                # instantiate the task proxy object
                itask = self.config.get_task_proxy( name, c_time, 'waiting', startup=False )

                # the initial task cycle time can be altered during
                # creation, so we have to create the task before
                # checking if stop time has been reached.
                skip = False
                if self.stop_time:
                    if int( itask.c_time ) > int( self.stop_time ):
                        itask.log( 'WARNING', " STOPPING at " + self.stop_time )
                        itask.prepare_for_death()
                        del itask
                        skip = True
                if not skip:
                    self.insert( itask )

        #except NamingError, e:
        except Exception, e:
            # A failed remote insertion should not bring the suite down
            # under any circumstances (e.g. requests to insert undefined
            # tasks).
            print 'INSERTION FAILED:', e
            print 

    def purge( self, id, stop ):
        # Remove an entire dependancy tree rooted on the target task,
        # through to the given stop time (inclusive). In general this
        # involves tasks that do not even exist yet within the pool.

        # Method: trigger the target task *virtually* (i.e. without
        # running the real task) by: setting it to the finished state,
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

        for itask in self.tasks:
            # Find the target task
            if itask.id == id:
                # set it finished
                itask.set_finished()
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
            for itask in self.tasks:
                current_time = self.clock.get_datetime()
                if itask.ready_to_run( current_time ) and int( itask.c_time ) <= int( stop ):
                    something_triggered = True
                    itask.set_finished()
                    foo = self.force_spawn( itask )
                    if foo:
                        spawn.append( foo )
                    die.append( itask.id )
 
        # reset any prerequisites "virtually" satisfied during the purge
        for task in spawn:
            task.prerequisites.set_all_unsatisfied()

        # finally, purge all tasks marked as depending on the target
        self.kill( die, dump_state=False )

    def check_timeouts( self, current_time ):
        for itask in self.tasks:
            itask.check_timeout(current_time)

    def waiting_contact_task_ready( self, current_time ):
        # This method actually returns True if ANY task is ready to run,
        # not just contact tasks. However, this should not be a problem.
        result = False
        for itask in self.tasks:
            #print itask.id, current_time
            if itask.ready_to_run(current_time):
                result = True
                break
        return result

    def kill_cycle( self, ctime ):
        # kill all tasks currently at ctime
        task_ids = []
        for itask in self.tasks:
            if itask.c_time == ctime: # and itask.get_status() == 'waiting':
                task_ids.append( itask.id )

        self.kill( task_ids )

    def spawn_and_die_cycle( self, ctime ):
        # spawn and kill all tasks currently at ctime
        task_ids = {}
        for itask in self.tasks:
            if itask.c_time == ctime: # and itask.get_status() == 'waiting':
                task_ids[ itask.id ] = True

        self.spawn_and_die( task_ids )


    def spawn_and_die( self, task_ids, dump_state=True, reason='suicide by remote request' ):
        # spawn and kill all tasks in task_ids.keys()
        # works for dict or list input

        # TO DO: clean up use of spawn_and_die (the keyword args are clumsy)

        if dump_state:
            self.log.warning( 'pre-spawn-and-die state dump: ' + self.dump_state( new_file = True ))

        for id in task_ids:
            # find the task
            found = False
            itask = None
            for t in self.tasks:
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
 
                if self.stop_time and int( new_task.c_time ) > int( self.stop_time ):
                    # we've reached the stop time: delete the new task 
                    new_task.log( 'WARNING', 'STOPPING at configured stop time' )
                    new_task.prepare_for_death()
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
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
            for t in self.tasks:
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
                self.tasks.remove( task )
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
                self.tasks.append( task )
                # do not retry
                break

    def filter_initial_task_list( self, inlist ):
        included_by_rc  = self.config[ 'include task list'   ]
        excluded_by_rc  = self.config[ 'exclude task list'   ]
        included_by_cline = self.include_via_cline 
        excluded_by_cline = self.exclude_via_cline 
        outlist = []

        include_list_supplied = False
        if len( included_by_cline ) > 0 or len( included_by_rc ) > 0:
            include_list_supplied = True
            included_tasks = included_by_cline + included_by_rc

        for name in inlist:
            if name in excluded_by_cline or name in excluded_by_rc:
                continue
            if include_list_supplied:
                if name not in included_tasks:
                    continue
            outlist.append( name ) 

        return outlist

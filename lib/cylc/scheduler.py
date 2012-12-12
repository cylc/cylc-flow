#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

from cylc_pyro_server import pyro_server
from task_types import task, clocktriggered
from prerequisites.plain_prerequisites import plain_prerequisites
from suite_host import suite_host
from owner import user
from cycle_time import ct, CycleTimeError
import datetime
import port_scan
import accelerated_clock 
import logging
import re, os, sys, shutil
from state_summary import state_summary
from remote_switch import remote_switch
from passphrase import passphrase
from OrderedDict import OrderedDict
from locking.lockserver import lockserver
from locking.suite_lock import suite_lock
from suite_id import identifier
from config import config, SuiteConfigError, TaskNotDefinedError
from global_config import globalcfg
from port_file import port_file, PortFileExistsError, PortFileError
from broker import broker
from Pyro.errors import NamingError, ProtocolError
from version import cylc_version
from regpath import RegPath
from CylcError import TaskNotFoundError, TaskStateError
from RuntimeGraph import rGraph
from RunEventHandler import RunHandler
from LogDiagnosis import LogSpec
from broadcast import broadcast
from suite_state_dumping import dumper
from suite_logging import suite_log
from suite_output import suite_output

class SchedulerError( Exception ):
    """
    Attributes:
        message - what the problem is. 
        TO DO: element - config element causing the problem
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class pool(object):
    def __init__( self, suite, config, wireless, pyro, log, run_mode, verbose, debug=False ):
        self.pyro = pyro
        self.run_mode = run_mode
        self.log = log
        self.verbose = verbose
        self.debug = debug
        self.qconfig = config['scheduling']['queues'] 
        self.config = config
        self.n_max_sub = config['cylc']['maximum simultaneous job submissions']
        self.assign()
        self.wireless = wireless

    def assign( self, reload=False ):
        # self.myq[taskname] = 'foo'
        # self.queues['foo'] = [live tasks in queue foo]

        self.myq = {}
        for queue in self.qconfig:
            for taskname in self.qconfig[queue]['members']:
                self.myq[taskname] = queue

        if not reload:
            self.queues = {}
        else:
            # reassign live tasks from the old queues to the new
            self.new_queues = {}
            for queue in self.queues:
                for itask in self.queues[queue]:
                    myq = self.myq[itask.name]
                    if myq not in self.new_queues:
                        self.new_queues[myq] = [itask]
                    else:
                        self.new_queues[myq].append( itask )
            self.queues = self.new_queues

    def add( self, itask ):
        try:
            self.pyro.connect( itask, itask.id )
        except NamingError, x:
            # Attempted insertion of a task that already exists.
            print >> sys.stderr, x
            self.log.critical( itask.id + ' CANNOT BE INSERTED (already exists)' )
            return
        except Exception, x:
            print >> sys.stderr, x
            self.log.critical( itask.id + ' CANNOT BE INSERTED (unknown error)' )
            return

        # add task to the appropriate queue
        queue = self.myq[itask.name]
        if queue not in self.queues:
            self.queues[queue] = [itask]
        else:
            self.queues[queue].append(itask)
        task.task.state_changed = True
        itask.log('DEBUG', "task proxy inserted" )

    def remove( self, task, reason ):
        # remove a task from the pool
        try:
            self.pyro.disconnect( task )
        except NamingError, x:
            # Attempted removal of a task that does not exist.
            print >> sys.stderr, x
            self.log.critical( task.id + ' CANNOT BE REMOVED (no such task)' )
            return
        except Exception, x:
            print >> sys.stderr, x
            self.log.critical( task.id + ' CANNOT BE REMOVED (unknown error)' )
            return
        task.prepare_for_death()
        # remove task from its queue
        queue = self.myq[task.name]
        self.queues[queue].remove( task )
        task.log( 'DEBUG', "task proxy removed (" + reason + ")" )
        del task

    def get_tasks( self ):
        tasks = []
        for queue in self.queues:
            tasks += self.queues[queue]
        #tasks.sort() # sorting any use here?
        return tasks

    def process( self ):
        readytogo = []
        for queue in self.queues:
            n_active = 0
            n_limit = self.qconfig[queue]['limit']
            for itask in self.queues[queue]:
                if n_limit:
                    # there is a limit on this queue
                    if itask.state.is_currently('submitted') or itask.state.is_currently('running'):
                        # count active tasks in this queue
                        n_active += 1
                    # compute difference from the limit
                    n_release = n_limit - n_active
                    if n_release <= 0:
                        # the limit is currently full
                        continue
            for itask in self.queues[queue]:
                if itask.ready_to_run():
                    if n_limit:
                        if n_release > 0:
                            n_release -= 1
                            readytogo.append(itask)
                        else:
                            itask.state.set_status('queued')
                    else:
                        readytogo.append(itask)

        if len(readytogo) == 0:
            if self.verbose:
                print "(No tasks ready to run)"
            return []

        print
        n_tasks = len(readytogo)
        print n_tasks, 'TASKS READY TO BE SUBMITTED'
        n_max = self.n_max_sub
        if n_tasks > n_max:
            print 'BATCHING: maximum simultaneous job submissions is set to', n_max
        batches, remainder = divmod( n_tasks, n_max )
        for i in range(0,batches):
            start = i*n_max
            self.batch_submit( readytogo[start:start+n_max] )
        if remainder != 0:
            self.batch_submit( readytogo[batches*n_max:n_tasks] )
        return readytogo

    def batch_submit( self, tasks ):
        if self.run_mode == 'simulation':
            for itask in tasks:
                print
                print 'TASK READY:', itask.id 
                itask.incoming( 'NORMAL', itask.id + ' started' )
            return

        before = datetime.datetime.now()
        ps = []
        n_fail = 0
        for itask in tasks:
            print
            print 'TASK READY:', itask.id 
            p = itask.submit( debug=self.debug, overrides=self.wireless.get(itask.id) )
            if p:
                ps.append( (itask,p) ) 
            else:
                n_fail += 1

        print
        print 'WAITING ON JOB SUBMISSIONS'
        n_succ = 0
        for itask, p in ps:
            res = p.wait()
            if res < 0:
                print >> sys.stderr, "ERROR: Task", itask.id, "job submission terminated by signal", res
                itask.reset_state_failed()
                itask.set_submit_failed()
                task.task.state_changed = True
                n_fail += 1
            elif res > 0:
                print >> sys.stderr, "ERROR: Task", itask.id, "job submission failed", res
                itask.reset_state_failed()
                itask.set_submit_failed()
                task.task.state_changed = True
                n_fail += 1
            else:
                n_succ += 1
                if self.verbose:
                    print "Task", itask.id, "job submission succeeded"

        after = datetime.datetime.now()
        n_tasks = len(tasks)
        print 'JOB SUBMISSIONS COMPLETED:'
        print "  Time taken: " + str( after - before )
        print " ", n_succ, "of", n_tasks, "job submissions succeeded" 
        if n_fail != 0:
            print " ", n_fail, "of", n_tasks, "job submissions failed" 

class scheduler(object):
    def __init__( self, is_restart=False ):

        # SUITE OWNER
        self.owner = user

        # SUITE HOST
        self.host= suite_host

        # STARTUP BANNER
        self.banner = OrderedDict()

        # DEPENDENCY BROKER
        self.broker = broker()

        self.lock_acquired = False

        self.is_restart = is_restart

        self.graph_warned = {}

        # COMMANDLINE OPTIONS

        self.parser.add_option( "--until", 
                help="Shut down after all tasks have PASSED this cycle time.",
                metavar="CYCLE", action="store", dest="stop_tag" )

        self.parser.add_option( "--hold", help="Hold (don't run tasks) "
                "immediately on starting.",
                action="store_true", default=False, dest="start_held" )

        self.parser.add_option( "--hold-after",
                help="Hold (don't run tasks) AFTER this cycle time.",
                metavar="CYCLE", action="store", dest="hold_time" )

        self.parser.add_option( "-m", "--mode",
                help="Run mode: live, simulation, or dummy; default is live.",
                metavar="STRING", action="store", default='live', dest="run_mode" )

        self.parser.add_option( "--reference-log", 
                help="Generate a reference log for use in reference tests.",
                action="store_true", default=False, dest="genref" )

        self.parser.add_option( "--reference-test", 
                help="Do a test run against a previously generated reference log.",
                action="store_true", default=False, dest="reftest" )

        self.parser.add_option( "--timing", help=\
                "Turn on main task processing loop timing.",
                action="store_true", default=False, dest="timing" )

        self.parser.add_option( "--from-gui", help=\
                "(do not use).",
                action="store_true", default=False, dest="from_gui" )

        self.parser.add_option( "--no-redirect", help=\
                "Do not redirect stdout and stderr to file.",
                action="store_true", default=False, dest="noredirect" )

        self.parse_commandline()

        # global config
        self.globals = globalcfg()
        # parse the suite definition
        self.configure_suite()

        reqmode = self.config['cylc']['required run mode']
        if reqmode:
            if reqmode != self.run_mode:
                raise SchedulerError, 'ERROR: this suite requires the ' + reqmode + ' run mode'
        
        self.reflogfile = os.path.join(self.config.dir,'reference.log')

        if self.options.genref:
            self.config['cylc']['log resolved dependencies'] = True

        elif self.options.reftest:
            req = self.config['cylc']['reference test']['required run mode']
            if req and req != self.run_mode:
                raise SchedulerError, 'ERROR: this suite allows only ' + req + ' mode reference tests'
            handler = self.config.event_handlers['shutdown']
            if handler: 
                print >> sys.stderr, 'WARNING: replacing shutdown event handler for reference test run'
            self.config.event_handlers['shutdown'] = self.config['cylc']['reference test']['suite shutdown event handler']
            self.config['cylc']['log resolved dependencies'] = True
            self.config.abort_if_shutdown_handler_fails = True
            spec = LogSpec( self.reflogfile )
            self.start_tag = spec.get_start_tag()
            self.stop_tag = spec.get_stop_tag()
            self.ref_test_allowed_failures = self.config['cylc']['reference test']['expected task failures']
            if not self.config['cylc']['reference test']['allow task failures'] and len( self.ref_test_allowed_failures ) == 0:
                self.config['cylc']['abort if any task fails'] = True
            self.config.abort_on_timeout = True
            timeout = self.config['cylc']['reference test'][ self.run_mode + ' mode suite timeout' ]
            if not timeout:
                raise SchedulerError, 'ERROR: suite timeout not defined for ' + self.run_mode + ' mode reference test'
            self.config.suite_timeout = timeout
            self.config.reset_timer = False

        # Note that the following lines must be present at the top of
        # the suite log file for use in reference test runs:
        self.log.critical( 'Suite starting at ' + str( datetime.datetime.now()) )
        if self.run_mode == 'live':
            self.log.info( 'Log event clock: real time' )
        else:
            self.log.info( 'Log event clock: accelerated' )
        self.log.info( 'Run mode: ' + self.run_mode )
        self.log.info( 'Start tag: ' + str(self.start_tag) )
        self.log.info( 'Stop tag: ' + str(self.stop_tag) )

        if self.start_tag:
            self.start_tag = self.ctexpand( self.start_tag)
        if self.stop_tag:
            self.stop_tag = self.ctexpand( self.stop_tag)

        self.runahead_limit = self.config.get_runahead_limit()
        self.asynchronous_task_list = self.config.get_asynchronous_task_name_list()

        # RECEIVER FOR BROADCAST VARIABLES
        self.wireless = broadcast( self.config.family_hierarchy )
        self.pyro.connect( self.wireless, 'broadcast_receiver')

        self.pool = pool( self.suite, self.config, self.wireless, self.pyro, self.log, self.run_mode, self.verbose, self.options.debug )

        # LOAD TASK POOL ACCORDING TO STARTUP METHOD
        self.load_tasks()
        self.initial_oldest_ctime = self.get_oldest_c_time()

        # REMOTELY ACCESSIBLE SUITE STATE SUMMARY
        self.suite_state = state_summary( self.config, self.run_mode, self.initial_oldest_ctime, self.from_gui )
        self.pyro.connect( self.suite_state, 'state_summary')

        # initial cycle time
        if self.is_restart:
            self.ict = None
        else:
            if self.options.warm:
                if self.options.set_ict:
                    self.ict = self.start_tag
                else:
                    self.ict = None
            elif self.options.raw:
                self.ict = None
            else:
                self.ict = self.start_tag

        self.configure_environments()

        self.already_timed_out = False
        if self.config.suite_timeout:
            self.set_suite_timer()

        self.print_banner()

        self.suite_outputer = suite_output( self.suite )
        if not self.options.noredirect:
            self.suite_outputer.redirect()

        if self.config['visualization']['runtime graph']['enable']:
            self.runtime_graph = rGraph( self.suite, self.config, self.initial_oldest_ctime, self.start_tag )

        self.orphans = []
        self.reconfiguring = False
        self.nudge_timer_start = None
        self.nudge_timer_on = False
        self.auto_nudge_interval = 5 # seconds

    def set_suite_timer( self, reset=False ):
        now = datetime.datetime.now()
        self.suite_timer_start = now
        print str(self.config.suite_timeout) + " minute suite timer starts NOW:", str(now)

    def ctexpand( self, tag ):
        # expand truncated cycle times (2012 => 2012010100)
        try:
            # cycle time
            tag = ct(tag).get()
        except CycleTimeError,x:
            try:
                # async integer tag
                int( tag )
            except ValueError:
                raise SystemExit( "ERROR:, invalid task tag : " + tag )
            else:
                pass
        else:
            pass
        return tag

    def reconfigure( self ):
        # reload the suite definition while the suite runs
        old_task_list = self.config.get_task_name_list()
        self.configure_suite( reconfigure=True )
        new_task_list = self.config.get_task_name_list()

        # find any old tasks that have been removed from the suite
        self.orphans = []
        for name in old_task_list:
            if name not in new_task_list:
                self.orphans.append(name)
        # adjust the new suite config to handle the orphans
        self.config.adopt_orphans( self.orphans )
 
        self.runahead_limit = self.config.get_runahead_limit()
        self.asynchronous_task_list = self.config.get_asynchronous_task_name_list()
        self.pool.qconfig = self.config['scheduling']['queues']
        self.pool.n_max_sub = self.config['cylc']['maximum simultaneous job submissions']
        self.pool.verbose = self.verbose
        self.pool.assign( reload=True )
        self.suite_state.config = self.config
        self.configure_environments()
        self.print_banner( reload=True )
        self.reconfiguring = True
        for itask in self.pool.get_tasks():
            itask.reconfigure_me = True

    def reload_taskdefs( self ):
        found = False
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('running'):
                # do not reload running tasks as some internal state
                # (e.g. timers) not easily cloneable at the moment,
                # and it is possible to make changes to the task config
                # that would be incompatible with the running task.
                if itask.reconfigure_me:
                    found = True
                continue
            if itask.reconfigure_me:
                itask.reconfigure_me = False
                if itask.name in self.orphans:
                    # orphaned task
                    if itask.state.is_currently('waiting') or itask.state.is_currently('queued'):
                        # if not started running yet, remove it.
                        self.pool.remove( itask, '(task orphaned by suite reload)' )
                    else:
                        # set spawned already so it won't carry on into the future
                        itask.state.set_spawned()
                        self.log.warning( 'orphaned task will not continue: ' + itask.id  )
                else:
                    self.log.warning( 'RELOADING TASK DEFINITION FOR ' + itask.id  )
                    new_task = self.config.get_task_proxy( itask.name, itask.tag, itask.state.get_status(), None, False )
                    if itask.state.has_spawned():
                        new_task.state.set_spawned()
                    # succeeded tasks need their outputs set completed:
                    if itask.state.is_currently('succeeded'):
                        new_task.set_succeeded()
                    self.pool.remove( itask, '(suite definition reload)' )
                    self.pool.add( new_task )
        self.reconfiguring = found

    def parse_commandline( self ):
        self.banner[ 'SUITE NAME' ] = self.suite
        self.banner[ 'SUITE DEFN' ] = self.suiterc

        self.run_mode = self.options.run_mode
        self.banner['RUN MODE'] = self.run_mode

        # LOGGING LEVEL
        if self.options.debug:
            self.logging_level = logging.DEBUG
        else:
            self.logging_level = logging.INFO

        if self.options.from_gui:
            self.from_gui = True
        else:
            self.from_gui = False

    def configure_suite( self, reconfigure=False ):
        # LOAD SUITE CONFIG FILE
        self.config = config( self.suite, self.suiterc,
                self.options.templatevars,
                self.options.templatevars_file, run_mode=self.run_mode,
                verbose=self.verbose )
        self.config.create_directories()
        self.hold_before_shutdown = self.config['development']['hold before shutdown']

        self.run_dir = self.globals.cfg['run directory']
        self.banner[ 'SUITE RUN DIR' ] = self.run_dir

        self.stop_task = None

        # START and STOP CYCLE TIMES
        self.stop_tag = None
        self.stop_clock_time = None

        # (self.start_tag is set already if provided on the command line).
        if not self.start_tag:
            # No initial cycle time on the command line
            if self.config['scheduling']['initial cycle time']:
                # Use suite.rc initial cycle time
                self.start_tag = str(self.config['scheduling']['initial cycle time'])

        if self.options.stop_tag:
            # A final cycle time was provided on the command line.
            self.stop_tag = self.options.stop_tag
        elif self.config['scheduling']['final cycle time']:
            # Use suite.rc final cycle time
            self.stop_tag = str(self.config['scheduling']['final cycle time'])

        # could be async tags:
        ##if self.stop_tag:
        ##    self.stop_tag = ct( self.stop_tag ).get()
        ##if self.start_tag:
        ##    self.start_tag = ct( self.start_tag ).get()

        if not self.start_tag and not self.is_restart:
            print >> sys.stderr, 'WARNING: No initial cycle time provided - no cycling tasks will be loaded.'

        # PAUSE TIME?
        self.hold_suite_now = False
        self.hold_time = None
        if self.options.hold_time:
            # raises CycleTimeError:
            self.hold_time = ct( self.options.hold_time ).get()
            #    self.parser.error( "invalid cycle time: " + self.hold_time )
            self.banner[ 'Pausing at' ] = self.hold_time

        # USE LOCKSERVER?
        self.use_lockserver = self.config['cylc']['lockserver']['enable']
        self.lockserver_port = None
        if self.use_lockserver:
            # check that user is running a lockserver
            # DO THIS BEFORE CONFIGURING PYRO FOR THE SUITE
            # (else scan etc. will hang on the partially started suite).
            # raises port_scan.SuiteNotFound error:
            self.lockserver_port = lockserver( self.host ).get_port()

        # CONFIGURE SUITE PYRO SERVER
        suitename = self.suite
        # REMOTELY ACCESSIBLE SUITE IDENTIFIER
        suite_id = identifier( self.suite, self.owner )
        if not reconfigure:
            self.pyro = pyro_server( suitename, self.suite_dir, 
                    self.globals.cfg['pyro']['base port'],
                    self.globals.cfg['pyro']['maximum number of ports'] )
            self.port = self.pyro.get_port()
            self.pyro.connect( suite_id, 'cylcid', qualified = False )

            self.banner[ 'PORT' ] = self.port
            try:
                self.port_file = port_file( self.suite, self.port,
                    self.globals.cfg['pyro']['ports directory'],
                    self.verbose )
            except PortFileExistsError,x:
                print >> sys.stderr, x
                raise SchedulerError( 'ERROR: suite already running? (if not, delete the port file)' )

        # USE QUICK TASK ELIMINATION?
        self.use_quick = self.config['development']['use quick task elimination']

        # ALLOW MULTIPLE SIMULTANEOUS INSTANCES?
        self.exclusive_suite_lock = not self.config['cylc']['lockserver']['simultaneous instances']

        # set suite in task class (for passing to task even hook scripts)
        task.task.suite = self.suite

        # Running in UTC time? (else just use the system clock)
        self.utc = self.config['cylc']['UTC mode']

        # ACCELERATED CLOCK for simulation and dummy run modes
        rate = self.config['cylc']['accelerated clock']['rate']
        offset = self.config['cylc']['accelerated clock']['offset']
        disable = self.config['cylc']['accelerated clock']['disable']
        if self.run_mode == 'live':
            disable = True
        if not reconfigure:
            self.clock = accelerated_clock.clock( int(rate), int(offset), self.utc, disable ) 
            task.task.clock = self.clock
            clocktriggered.clocktriggered.clock = self.clock
            self.pyro.connect( self.clock, 'clock' )

        self.state_dumper = dumper( self.suite, self.run_mode, self.clock, self.start_tag, self.stop_tag )
        self.state_dump_dir = self.state_dumper.get_dir()
        self.state_dump_filename = self.state_dumper.get_path()

        if not reconfigure:
            # REMOTE CONTROL INTERFACE
            # (note: passing in self to give access to task pool methods is a bit clunky?).
            self.remote = remote_switch( self.config, self.clock, self.suite_dir, self )
            self.pyro.connect( self.remote, 'remote' )

            slog = suite_log( self.suite )
            slog.pimp( self.logging_level, self.clock )
            self.log = slog.get_log()
            self.logfile = slog.get_path()
            self.logdir = slog.get_dir()
        else:
            self.remote.config = self.config

    def configure_environments( self ):
        cylcenv = OrderedDict()
        cylcenv[ 'CYLC_DIR_ON_SUITE_HOST' ] = os.environ[ 'CYLC_DIR' ]
        cylcenv[ 'CYLC_MODE' ] = 'scheduler'
        cylcenv[ 'CYLC_DEBUG' ] = str( self.options.debug )
        cylcenv[ 'CYLC_VERBOSE' ] = str(self.verbose)
        cylcenv[ 'CYLC_SUITE_HOST' ] =  str( self.host )
        cylcenv[ 'CYLC_SUITE_PORT' ] =  str( self.pyro.get_port())
        cylcenv[ 'CYLC_SUITE_REG_NAME' ] = self.suite
        cylcenv[ 'CYLC_SUITE_REG_PATH' ] = RegPath( self.suite ).get_fpath()
        cylcenv[ 'CYLC_SUITE_OWNER' ] = self.owner
        cylcenv[ 'CYLC_USE_LOCKSERVER' ] = str( self.use_lockserver )
        cylcenv[ 'CYLC_LOCKSERVER_PORT' ] = str( self.lockserver_port ) # "None" if not using lockserver
        cylcenv[ 'CYLC_UTC' ] = str(self.utc)
        cylcenv[ 'CYLC_SUITE_INITIAL_CYCLE_TIME' ] = str( self.ict ) # may be "None"
        cylcenv[ 'CYLC_SUITE_FINAL_CYCLE_TIME'   ] = str( self.stop_tag  ) # may be "None"
        cylcenv[ 'CYLC_SUITE_DEF_PATH_ON_SUITE_HOST' ] = self.suite_dir
        cylcenv[ 'CYLC_SUITE_DEF_PATH' ] = self.suite_dir
        cylcenv[ 'CYLC_SUITE_LOG_DIR' ] = self.logdir
        task.task.cylc_env = cylcenv

        # Put suite identity variables (for event handlers executed by
        # cylc) into the environment in which cylc runs
        for var in cylcenv:
            os.environ[var] = cylcenv[var]

        # Suite bin directory for event handlers executed by the scheduler. 
        os.environ['PATH'] = self.suite_dir + '/bin:' + os.environ['PATH'] 
        # User defined local variables that may be required by event handlers
        senv = self.config['cylc']['environment']
        for var in senv:
            os.environ[var] = os.path.expandvars(senv[var])


    def print_banner( self, reload=False ):
        msg = []
        if not reload:
            msg.append( "_" )
            msg.append( "The cylc suite engine, version " + cylc_version )
            msg.append( "Home page: http://cylc.github.com/cylc" )
            msg.append( "-" )
            msg.append( "Copyright (C) 2008-2012 Hilary Oliver, NIWA" )
            msg.append( "-" )
            msg.append( "This program comes with ABSOLUTELY NO WARRANTY; for details type:" )
            msg.append( " `cylc license warranty'." )
            msg.append( "This is free software, and you are welcome to redistribute it under" )
            msg.append( "certain conditions; for details type:" )
            msg.append( " `cylc license conditions'." )
            msg.append( "-" )
        else:
            msg.append( "_" )
            msg.append( "RELOADING THE SUITE DEFINITION AT RUNTIME" )
            msg.append( "-" )
 
        lenm = 0
        for m in msg:
            if len(m) > lenm:
                lenm = len(m)
        uline = '_' * lenm
        vline = '-' * lenm

        for m in msg:
            if m == '_':
                print uline
            elif m == '-':
                print vline
            else:
                print m

        items = self.banner.keys()

        longest_item = items[0]
        for item in items:
            if len(item) > len(longest_item):
                longest_item = item

        template = re.sub( '.', '.', longest_item )

        for item in self.banner.keys():
            print ' o ', re.sub( '^.{' + str(len(item))+ '}', item, template) + '...' + str( self.banner[ item ] )

    def run( self ):
        if self.use_lockserver:
            suitename = self.suite

            # request suite access from the lock server
            if suite_lock( suitename, self.suite_dir, self.host, self.lockserver_port, 'scheduler' ).request_suite_access( self.exclusive_suite_lock ):
               self.lock_acquired = True
            else:
               raise SchedulerError( "Failed to acquire a suite lock" )

        if self.hold_time:
            # TO DO: HANDLE STOP AND PAUSE TIMES THE SAME WAY?
            self.hold_suite( self.hold_time )

        if self.options.start_held:
            self.log.warning( "Held on start-up (no tasks will be submitted)")
            self.hold_suite()
        else:
            print "\nSTARTING"

        handler = self.config.event_handlers['startup']
        if handler:
            if self.config.abort_if_startup_handler_fails:
                foreground = True
            else:
                foreground = False
            try:
                RunHandler( 'startup', handler, self.suite, msg='suite starting', fg=foreground )
            except Exception, x:
                # Note: test suites depends on this message:
                print >> sys.stderr, '\nERROR: startup EVENT HANDLER FAILED'
                raise SchedulerError, x

        while True: # MAIN LOOP
            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.

            if self.reconfiguring:
                # user has requested a suite definition reload
                self.reload_taskdefs()

            if self.process_tasks():
                self.log.debug( "ENTERING TASK PROCESSING" )
                if self.options.timing:
                    # loop timing: use real clock even in sim mode
                    main_loop_start_time = datetime.datetime.now()

                self.negotiate()

                submitted = self.pool.process()
                self.process_resolved( submitted )

                if not self.config['development']['disable task elimination']:
                    self.cleanup()
                self.spawn()
                self.state_dumper.dump( self.pool.get_tasks(), self.wireless )

                self.update_state_summary()

                # expire old broadcast variables
                self.wireless.expire( self.get_oldest_c_time() )

                if self.options.timing:
                    delta = datetime.datetime.now() - main_loop_start_time
                    seconds = delta.seconds + float(delta.microseconds)/10**6
                    print "MAIN LOOP TIME TAKEN:", seconds, "seconds"

            # REMOTE METHOD HANDLING; with no timeout and single- threaded pyro,
            # handleRequests() returns after one or more remote method
            # invocations are processed (these are not just task messages, hence
            # the use of the state_changed variable below).
            # HOWEVER, we now need to check if clock-triggered tasks are ready
            # to trigger according on wall clock time, so we also need a
            # timeout to handle this when nothing else is happening.

            # incoming task messages set task.task.state_changed to True
            #print 'Pyro>'
            self.pyro.handleRequests(timeout=1)
            #print '<Pyro'
            if task.task.progress_msg_rec:
                task.task.progress_msg_rec = False
                self.update_state_summary()

            if self.config.suite_timeout:
                self.check_suite_timer()

            # SHUT DOWN IF ALL TASKS ARE SUCCEEDED OR HELD
            stop_now = True  # assume stopping

            #if stop_now:                 
            if True:
                if self.hold_suite_now or self.hold_time:
                    # don't stop if the suite is held
                    stop_now = False
                for itask in self.pool.get_tasks():
                    # find any reason not to stop
                    if not itask.state.is_currently('succeeded') and not itask.state.is_currently('held'):
                        # don't stop if any tasks are waiting, submitted, or running
                        stop_now = False
                        break
                for itask in self.pool.get_tasks():
                    if not itask.is_cycling:
                        continue
                    if itask.state.is_currently('succeeded') and not itask.state.has_spawned():
                        # Check for tasks that are succeeded but not spawned.
                        # If they are older than the suite stop time they
                        # must be about to spawn. Otherwise they must be 
                        # stalled at the runahead limit, in which case we
                        # can stop.
                        if self.stop_tag:
                            if int(itask.tag) < int(self.stop_tag):
                                stop_now = False
                                break
                        else:
                            stop_now = False
                            break

            if self.config['cylc']['abort if any task fails']:
                if self.any_task_failed():
                    raise SchedulerError( 'One or more tasks failed, and this suite sets "abort if any task fails"' )

            if self.options.reftest:
                if len( self.ref_test_allowed_failures ) > 0:
                    for itask in self.get_failed_tasks():
                        if itask.id not in self.ref_test_allowed_failures:
                            print >> sys.stderr, itask.id
                            raise SchedulerError( 'A task failed unexpectedly: not in allowed failures list' )

            if stop_now:
                if self.hold_before_shutdown:
                    self.log.warning( "ALL RUNNING TASKS FINISHED but HOLD-BEFORE-SHUTDOWN is ON" )
                    self.hold_suite()
                else:
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
                for itask in self.pool.get_tasks():
                    if itask.name == name:
                        if not itask.state.is_currently('succeeded'):
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

        # END MAIN LOOP
        self.log.critical( "Suite shutting down at " + str(datetime.datetime.now()) )

        if self.options.genref:
            print '\nCOPYING REFERENCE LOG to suite definition directory'
            from shutil import copy
            copy( self.logfile, self.reflogfile)

    def update_state_summary( self ):
        self.log.debug( "UPDATING STATE SUMMARY" )
        self.suite_state.update( self.pool.get_tasks(), self.clock,
                self.get_oldest_c_time(), self.get_newest_c_time(), self.paused(),
                self.will_pause_at(), self.remote.halt,
                self.will_stop_at(), self.runahead_limit )

    def process_resolved( self, tasks ):
        # process resolved dependencies (what actually triggers off what at run time).
        for itask in tasks:
            if self.config['visualization']['runtime graph']['enable']:
                self.runtime_graph.update( itask, self.get_oldest_c_time(), self.get_oldest_async_tag() )
            if self.config['cylc']['log resolved dependencies']:
                itask.log( 'NORMAL', 'triggered off ' + str( itask.get_resolved_dependencies()) )

    def check_suite_timer( self ):
        if self.already_timed_out:
            return
        now = datetime.datetime.now()
        timeout = self.suite_timer_start + datetime.timedelta( minutes=self.config.suite_timeout )
        handler = self.config.event_handlers['timeout']
        if now > timeout:
            message = 'suite timed out after ' + str( self.config.suite_timeout) + ' minutes' 
            self.log.warning( message )
            if handler:
                # a handler is defined
                self.already_timed_out = True
                if self.config.abort_if_timeout_handler_fails:
                    foreground = True
                else:
                    foreground = False
                try:
                    RunHandler( 'timeout', handler, self.suite, msg=message, fg=foreground )
                except Exception, x:
                    # Note: tests suites depend on the following message:
                    print >> sys.stderr, '\nERROR: timeout EVENT HANDLER FAILED'
                    raise SchedulerError, x

            if self.config.abort_on_timeout:
                raise SchedulerError, 'Abort on suite timeout is set'

    def process_tasks( self ):
        # do we need to do a pass through the main task processing loop?
        process = False
        if self.run_mode == 'simulation':
            for itask in self.pool.get_tasks():
                    itask.sim_time_check()

        if task.task.state_changed:
            process = True
            task.task.state_changed = False
            # a task changing state indicates new suite activity
            # so reset the suite timer.
            if self.config.suite_timeout and self.config.reset_timer:
                self.set_suite_timer()

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

        ##if not process:
        ##    # If we neglect to set task.state_changed on some event that 
        ##    # makes re-negotiation of dependencies necessary then if
        ##    # that event ever happens in isolation the suite could stall
        ##    # unless manually nudged ("cylc nudge SUITE").  If this
        ##    # happens turn on debug logging to see what happens
        ##    # immediately before the stall, then set task.state_changed
        ##    # = True in the corresponding code section. Alternatively,
        ##    # for an undiagnosed stall you can uncomment this section to 
        ##    # stimulate task processing every few seconds even during
        ##    # lulls in activity.  THIS SHOULD NOT BE NECESSARY, HOWEVER.
        ##    if not self.nudge_timer_on:
        ##        self.nudge_timer_start = datetime.datetime.now()
        ##        self.nudge_timer_on = True
        ##    else:
        ##        timeout = self.nudge_timer_start + \
        ##              datetime.timedelta( seconds=self.auto_nudge_interval )
        ##      if datetime.datetime.now() > timeout:
        ##          process = True
        ##          self.nudge_timer_on = False

        return process

    def shutdown( self, message='' ):
        # called by main command
        print "\nSUITE SHUTTING DOWN"
        self.state_dumper.dump( self.pool.get_tasks(), self.wireless )
        if self.use_lockserver:
            # do this last
            suitename = self.suite

            if self.lock_acquired:
                print "Releasing suite lock"
                lock = suite_lock( suitename, self.suite_dir, self.host, self.lockserver_port, 'scheduler' )
                try:
                    if not lock.release_suite_access():
                        print >> sys.stderr, 'WARNING failed to release suite lock!'
                except port_scan.SuiteIdentificationError, x:
                    print >> sys.stderr, x
                    print >> sys.stderr, 'WARNING failed to release suite lock!'

        if self.pyro:
            self.pyro.shutdown()

        try:
            self.port_file.unlink()
        except PortFileError, x:
            # port file may have been deleted
            print >> sys.stderr, x

        if self.config['visualization']['runtime graph']['enable']:
            self.runtime_graph.finalize()

        print message

        handler = self.config.event_handlers['shutdown']
        if handler:
            if self.config.abort_if_shutdown_handler_fails:
                foreground = True
            else:
                foreground = False
            try:
                RunHandler( 'shutdown', handler, self.suite, msg=message, fg=foreground )
            except Exception, x:
                if self.options.reftest:
                    sys.exit( '\nERROR: SUITE REFERENCE TEST FAILED' )
                else:
                    # Note: tests suites depend on the following message:
                    sys.exit( '\nERROR: shutdown EVENT HANDLER FAILED' )
            else:
                print '\nSUITE REFERENCE TEST PASSED'

        if not self.options.noredirect:
            self.suite_outputer.restore()

    def get_tasks( self ):
        return self.pool.get_tasks()

    def set_stop_ctime( self, stop_tag ):
        self.log.warning( "Setting stop cycle time: " + stop_tag )
        self.stop_tag = stop_tag

    def set_stop_clock( self, dtime ):
        self.log.warning( "Setting stop clock time: " + dtime.isoformat() )
        self.stop_clock_time = dtime

    def set_stop_task( self, taskid ):
        self.log.warning( "Setting stop task: " + taskid )
        self.stop_task = taskid

    def hold_suite( self, ctime = None ):
        if ctime:
            self.log.warning( "Setting suite hold cycle time: " + ctime )
            self.hold_time = ctime
        else:
            self.hold_suite_now = True
            self.log.warning( "Holding all waiting or queued tasks now")
            for itask in self.pool.get_tasks():
                if itask.state.is_currently('queued') or itask.state.is_currently('waiting'):
                    # (not runahead: we don't want these converted to
                    # held or they'll be released immediately on restart)
                    itask.state.set_status('held')

    def release_suite( self ):
        if self.hold_suite_now:
            self.log.warning( "RELEASE: new tasks will be queued when ready")
            self.hold_suite_now = False
            self.hold_time = None
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('held'):
                if self.stop_tag and int( itask.c_time ) > int( self.stop_tag ):
                    # this task has passed the suite stop time
                    itask.log( 'NORMAL', "Not releasing (beyond suite stop cycle) " + self.stop_tag )
                elif itask.stop_c_time and int( itask.c_time ) > int( itask.stop_c_time ):
                    # this task has passed its own stop time
                    itask.log( 'NORMAL', "Not releasing (beyond task stop cycle) " + itask.stop_c_time )
                else:
                    # release this task
                    itask.state.set_status('waiting')
 
        # TO DO: write a separate method for cancelling a stop time:
        #if self.stop_tag:
        #    self.log.warning( "UNSTOP: unsetting suite stop time")
        #    self.stop_tag = None

    def will_stop_at( self ):
        if self.stop_tag:
            return self.stop_tag
        elif self.stop_clock_time:
            return self.stop_clock_time.isoformat()
        elif self.stop_task:
            return self.stop_task
        else:
            return None

    def clear_stop_times( self ):
        self.stop_tag = None
        self.stop_clock_time = None
        self.stop_task = None
 
    def paused( self ):
        return self.hold_suite_now

    def stopping( self ):
        if self.stop_tag or self.stop_clock_time:
            return True
        else:
            return False

    def will_pause_at( self ):
        return self.hold_time

    def get_runahead_base( self ):
        # Return the cycle time from which to compute the runahead
        # limit: take the oldest task not succeeded or failed (note this
        # excludes finished tasks and it includes runahead-limited tasks
        # - consequently "too low" a limit cannot actually stall a suite.
        oldest = '99991228235959'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if itask.state.is_currently('failed') or itask.state.is_currently('succeeded'):
                continue
            #if itask.is_daemon():
            #    # avoid daemon tasks
            #    continue
            if int( itask.c_time ) < int( oldest ):
                oldest = itask.c_time
        return oldest

    def get_oldest_async_tag( self ):
        # return the tag of the oldest non-daemon task
        oldest = 99999999999999
        for itask in self.pool.get_tasks():
            if itask.is_cycling():
                continue
            #if itask.state.is_currently('failed'):  # uncomment for earliest NON-FAILED 
            #    continue
            if itask.is_daemon():
                continue
            if int( itask.tag ) < oldest:
                oldest = int(itask.tag)
        return oldest

    def get_oldest_c_time( self ):
        # return the cycle time of the oldest task
        oldest = '99991228230000'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            #if itask.state.is_currently('failed'):  # uncomment for earliest NON-FAILED 
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
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            # avoid daemon tasks
            #if itask.is_daemon():
            #    continue
            if int( itask.c_time ) > int( newest ):
                newest = itask.c_time
        return newest

    def no_tasks_running( self ):
        # return True if no REAL tasks are submitted or running
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('running') or itask.state.is_currently('submitted'):
                if hasattr( itask, 'is_pseudo_task' ):
                    # ignore task families -their 'running' state just
                    # indicates existence of running family members.
                    continue
                else:
                    return False
        return True

    def get_failed_tasks( self ):
        failed = []
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('failed'):
                failed.append( itask )
        return failed

    def any_task_failed( self ):
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('failed'):
                return True
        return False

    def negotiate( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        # BROKERED NEGOTIATION is O(n) in number of tasks.

        self.broker.reset()

        for itask in self.pool.get_tasks():
            # register task outputs
            self.broker.register( itask )

        for itask in self.pool.get_tasks():
            # try to satisfy me (itask) if I'm not already satisfied.
            if itask.not_fully_satisfied():
                self.broker.negotiate( itask )

        for itask in self.pool.get_tasks():
            # (To Do: only used by repeating async tasks now)
            if not itask.not_fully_satisfied():
                itask.check_requisites()

    def release_runahead( self ):
        if self.runahead_limit:
            ouct = self.get_runahead_base() 
            for itask in self.pool.get_tasks():
                if not itask.is_cycling():
                    # TO DO: this test is not needed?
                    continue
                if itask.state.is_currently('runahead'):
                    foo = ct( itask.c_time )
                    foo.decrement( hours=self.runahead_limit )
                    if int( foo.get() ) < int( ouct ):
                        if self.hold_suite_now:
                            itask.log( 'DEBUG', "Releasing runahead (to held)" )
                            itask.state.set_status('held')
                        else:
                            itask.log( 'DEBUG', "Releasing runahead (to waiting)" )
                            itask.state.set_status('waiting')

    def check_hold_spawned_task( self, old_task, new_task ):
        if self.hold_suite_now:
            new_task.log( 'NORMAL', "HOLDING (general suite hold) " )
            new_task.state.set_status('held')
        elif self.stop_tag and int( new_task.c_time ) > int( self.stop_tag ):
            # we've reached the suite stop time
            new_task.log( 'NORMAL', "HOLDING (beyond suite stop cycle) " + self.stop_tag )
            new_task.state.set_status('held')
        elif self.hold_time and int( new_task.c_time ) > int( self.hold_time ):
            # we've reached the suite hold time
            new_task.log( 'NORMAL', "HOLDING (beyond suite hold cycle) " + self.hold_time )
            new_task.state.set_status('held')
        elif old_task.stop_c_time and int( new_task.c_time ) > int( old_task.stop_c_time ):
            # this task has a stop time configured, and we've reached it
            new_task.log( 'NORMAL', "HOLDING (beyond task stop cycle) " + old_task.stop_c_time )
            new_task.state.set_status('held')
        elif self.runahead_limit:
            ouct = self.get_runahead_base()
            foo = ct( new_task.c_time )
            foo.decrement( hours=self.runahead_limit )
            if int( foo.get() ) >= int( ouct ):
                # beyond the runahead limit
                new_task.plog( "HOLDING (runahead limit)" )
                new_task.state.set_status('runahead')

    def spawn( self ):
        # create new tasks foo(T+1) if foo has not got too far ahead of
        # the slowest task, and if foo(T) spawns
        for itask in self.pool.get_tasks():
            if itask.ready_to_spawn():
                itask.log( 'DEBUG', 'spawning')
                new_task = itask.spawn( 'waiting' )
                if itask.is_cycling():
                    self.check_hold_spawned_task( itask, new_task )
                    # perpetuate the task stop time, if there is one
                    new_task.stop_c_time = itask.stop_c_time
                self.pool.add( new_task )

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
            self.pool.add( new_task )
            return new_task

    def earliest_unspawned( self ):
        all_spawned = True
        earliest_unspawned = '99998877665544'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
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
        earliest_unsatisfied = '99998877665544'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
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
        earliest_unsucceeded = '99998877665544'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if itask.state.is_currently('failed'):
                # EXCLUDING FAILED TASKS
                continue
            #if itask.is_daemon():
            #   avoid daemon tasks
            #   continue

            if not itask.state.is_currently('succeeded'):
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

        # times of any failed tasks. 
        failed_rt = {}
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if itask.state.is_currently('failed'):
                failed_rt[ itask.c_time ] = True

        # suicide
        for itask in self.pool.get_tasks():
            if itask.suicide_prerequisites.count() != 0:
                if itask.suicide_prerequisites.all_satisfied():
                    self.spawn_and_die( [itask.id], dump_state=False, reason='suicide' )

        if self.use_quick:
            self.cleanup_non_intercycle( failed_rt )

        self.cleanup_generic( failed_rt )

        self.cleanup_async()

    def async_cutoff(self):
        cutoff = 0
        for itask in self.pool.get_tasks():
            if itask.is_cycling():
                continue
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
        for itask in self.pool.get_tasks():
            if itask.is_cycling():
                continue
            if itask.done() and itask.tag < cutoff:
                spent.append( itask )
        for itask in spent:
            self.pool.remove( itask, 'async spent' )

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

        # time of the earliest unspawned task
        [all_spawned, earliest_unspawned] = self.earliest_unspawned()
        if all_spawned:
            self.log.debug( "all tasks spawned")
        else:
            self.log.debug( "earliest unspawned task at: " + earliest_unspawned )

        # find the spent quick death tasks
        spent = []
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
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

            if hasattr( itask, 'is_pid' ):
                # Is there a later succeeded instance of the same task?
                # It must be SUCCEEDED in case the current task fails and
                # cannot be fixed => the task's manually inserted
                # post-gap successor will need to be satisfied by said
                # succeeded task. 
                there_is = False
                for t in self.pool.get_tasks():
                    if not t.is_cycling():
                        continue
                    if t.name == itask.name and \
                            int( t.c_time ) > int( itask.c_time ) and \
                            t.state.is_currently('succeeded'):
                                there_is = True
                                break
                if not there_is:
                    continue

            # and, by a process of elimination
            spent.append( itask )
 
        # delete the spent quick death tasks
        for itask in spent:
            self.pool.remove( itask, 'quick' )

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
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
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
            self.pool.remove( itask, 'general' )

    def trigger_task( self, task_id ):
        # Set a task to the 'ready' state (all prerequisites satisfied)
        # and tell clock-triggered tasks to trigger regardless of their
        # designated trigger time.
        found = False
        for itask in self.pool.get_tasks():
            # Find the task to trigger.
            if itask.id == task_id:
                found = True
                break
        if not found:
            raise TaskNotFoundError, "Task not present in suite: " + task_id
        # dump state
        self.log.warning( 'pre-trigger state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))
        itask.plog( "triggering now" )
        itask.reset_state_ready()
        if itask.is_clock_triggered():
            itask.set_trigger_now(True)

    def reset_task_state( self, task_id, state ):
        if state not in [ 'ready', 'waiting', 'succeeded', 'failed', 'held', 'spawn' ]:
            raise TaskStateError, 'Illegal reset state: ' + state
        found = False
        for itask in self.pool.get_tasks():
            # Find the task to reset.
            if itask.id == task_id:
                found = True
                break
        if not found:
            raise TaskNotFoundError, "Task not present in suite: " + task_id

        itask.plog( "resetting to " + state + " state" )

        self.log.warning( 'pre-reset state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))

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
        elif state == 'spawn':
            self.force_spawn(itask)

    def add_prerequisite( self, task_id, message ):
        # find the task to reset
        found = False
        for itask in self.pool.get_tasks():
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
                for jtask in self.pool.get_tasks():
                    if not jtask.is_cycling():
                        continue
                    if itask.id == jtask.id:
                        # task already in the suite
                        rject = True
                        break
                if rject:
                    rejected.append( itask.id )
                    itask.prepare_for_death()
                    del itask
                else: 
                    if self.stop_tag and int( itask.tag ) > int( self.stop_tag ):
                        itask.plog( "HOLDING at configured suite stop time " + self.stop_tag )
                        itask.state.set_status('held')
                    if itask.stop_c_time and int( itask.tag ) > int( itask.stop_c_time ):
                        # this task has a stop time configured, and we've reached it
                        itask.plog( "HOLDING at configured task stop time " + itask.stop_c_time )
                        itask.state.set_status('held')
                    inserted.append( itask.id )
                    to_insert.append(itask)

        if len( to_insert ) > 0:
            self.log.warning( 'pre-insertion state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))
            for jtask in to_insert:
                self.pool.add( jtask )
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

        self.log.warning( 'pre-purge state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))

        # Purge is an infrequently used power tool, so print 
        # comprehensive information on what it does to stdout.
        print
        print "PURGE ALGORITHM RESULTS:"

        die = []
        spawn = []

        print 'ROOT TASK:'
        for itask in self.pool.get_tasks():
            # Find the target task
            if itask.id == id:
                # set it succeeded
                print '  Setting', itask.id, 'succeeded'
                itask.set_succeeded()
                # force it to spawn
                print '  Spawning', itask.id
                foo = self.force_spawn( itask )
                if foo:
                    spawn.append( foo )
                # mark it for later removal
                print '  Marking', itask.id, 'for deletion'
                die.append( id )
                break

        print 'VIRTUAL TRIGGERING'
        # trace out the tree of dependent tasks
        something_triggered = True
        while something_triggered:
            self.negotiate()
            something_triggered = False
            for itask in self.pool.get_tasks():
                if int( itask.tag ) > int( stop ):
                    continue
                if itask.ready_to_run():
                    something_triggered = True
                    print '  Triggering', itask.id
                    itask.set_succeeded()
                    print '  Spawning', itask.id
                    foo = self.force_spawn( itask )
                    if foo:
                        spawn.append( foo )
                    print '  Marking', itask.id, 'for deletion'
                    # kill these later (their outputs may still be needed)
                    die.append( itask.id )
                elif itask.suicide_prerequisites.count() > 0:
                    if itask.suicide_prerequisites.all_satisfied():
                        print '  Spawning virtually activated suicide task', itask.id
                        self.force_spawn( itask )
                        # kill these now (not setting succeeded; outputs not needed)
                        print '  Suiciding', itask.id, 'now'
                        self.kill( [itask.id], dump_state=False )

        # reset any prerequisites "virtually" satisfied during the purge
        print 'RESETTING spawned tasks to unsatisified:'
        for itask in spawn:
            print '  ', itask.id
            itask.prerequisites.set_all_unsatisfied()

        # finally, purge all tasks marked as depending on the target
        print 'REMOVING PURGED TASKS:'
        for id in die:
            print '  ', id
        self.kill( die, dump_state=False )

        print 'PURGE DONE'

    def check_timeouts( self ):
        for itask in self.pool.get_tasks():
            itask.check_submission_timeout()
            itask.check_execution_timeout()

    def waiting_clocktriggered_task_ready( self ):
        # This method actually returns True if ANY task is ready to run,
        # not just clocktriggered tasks. However, this should not be a problem.
        result = False
        for itask in self.pool.get_tasks():
            #print itask.id
            if itask.ready_to_run():
                result = True
                break
        return result

    def kill_cycle( self, tag ):
        # kill all tasks currently with given tag
        task_ids = []
        for itask in self.pool.get_tasks():
            if itask.tag == tag:
                task_ids.append( itask.id )
        self.kill( task_ids )

    def spawn_and_die_cycle( self, tag ):
        # spawn and kill all tasks currently with given tag
        task_ids = {}
        for itask in self.pool.get_tasks():
            if itask.tag == tag:
                task_ids[ itask.id ] = True
        self.spawn_and_die( task_ids )

    def spawn_and_die( self, task_ids, dump_state=True, reason='remote request' ):
        # Spawn and kill all tasks in task_ids. Works for dict or list input.
        # TO DO: clean up use of spawn_and_die (the keyword args are clumsy)

        if dump_state:
            self.log.warning( 'pre-spawn-and-die state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))

        for id in task_ids:
            # find the task
            found = False
            itask = None
            for t in self.pool.get_tasks():
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
 
                if self.stop_tag and int( new_task.tag ) > int( self.stop_tag ):
                    # we've reached the stop time
                    new_task.plog( 'HOLDING at configured suite stop time' )
                    new_task.state.set_status('held')
                # perpetuate the task stop time, if there is one
                new_task.stop_c_time = itask.stop_c_time
                self.pool.add( new_task )
            else:
                # already spawned: the successor already exists
                pass

            # now kill the task
            self.pool.remove( itask, reason )

    def kill( self, task_ids, dump_state=True ):
        # kill without spawning all tasks in task_ids
        if dump_state:
            self.log.warning( 'pre-kill state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))
        for id in task_ids:
            # find the task
            found = False
            itask = None
            for t in self.pool.get_tasks():
                if t.id == id:
                    found = True
                    itask = t
                    break
            if not found:
                self.log.warning( "task to kill not found: " + id )
                return
            self.pool.remove( itask, 'by request' )

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


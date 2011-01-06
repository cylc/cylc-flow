#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import re, os, sys, shutil
import socket
import logging
import datetime
import port_scan
from cylcrc import preferences
from execute import execute
import cycle_time
import cylc_pyro_server
import dead_letter
import state_summary
import accelerated_clock 
from job_submit import job_submit
from registration import registrations
from lockserver import lockserver
from suite_lock import suite_lock
from suite_id import identifier
from OrderedDict import OrderedDict
from mkdir_p import mkdir_p
import task

class scheduler(object):

    def __init__( self ):
        self.banner = {}
        self.pyro = None
        self.use_lockserver = False
        self.lock_acquired = False

        # PROVIDE IN DERIVED CLASSES:
        # self.parser = OptionParser( usage )

        self.parser.set_defaults( dummy_mode=False, practice_mode=False,
                include=None, exclude=None, debug=False,
                clock_rate=10, clock_offset=24, dummy_run_length=20 )

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

        self.parser.add_option( "--clock-rate", 
                help="(DUMMY and PRACTICE modes) accelerated clock rate: RATE seconds of "
                "real time per simulated hour (default 10).",
                metavar="RATE", action="store", dest="clock_rate" )

        self.parser.add_option( "--clock-offset", 
                help="(DUMMY and PRACTICE modes) start the accelerated clock at HOURS "
                "prior to the initial cycle time (default 24 hours). "
                "This simulates catch up to real time operation.",
                metavar="HOURS", action="store", dest="clock_offset" )

        self.parser.add_option( "--fail", help=\
                "(DUMMY MODE) get task NAME at cycle time CYCLE to report failure "
                "and then abort. Use this to test failure and recovery scenarios.",
                metavar="NAME%CYCLE", action="store", dest="failout_task_id" )

        self.parser.add_option( "--dummy-task-run-length", help=\
                "(DUMMY MODE) change the length of run time, relative to the dummy "
                "mode clock, of each running task. The default is 20 minutes.",
                metavar="MINUTES", action="store", dest="dummy_run_length" )

        self.parser.add_option( "--debug", help=\
                "Turn on the 'debug' logging level and print the Python "
                "source traceback for unhandled exceptions (otherwise "
                "just the error message will be printed).",
                action="store_true", dest="debug" )

        self.parser.add_option( "--timing", help=\
                "Turn on main task processing loop timing, which may be useful "
                "for testing very large suites of 1000+ tasks.",
                action="store_true", default=False, dest="timing" )

        self.parser.add_option( "--graphfile", help=\
                "Write a suite dependency graph in the dot language "
                "for the graphviz package - see comments at the head "
                "of the resulting file. WARNING: the dependency graph "
                "is continually updated: use this only for short runs!"
                "FILENAME should be an absolute path or relative to $HOME",
                metavar="FILENAME", action="store", default=None,
                dest="graphfile" )

        self.parse_commandline()

    def print_banner( self ):
        print "_______________________________________________"
        print "_ Cylc Self Organising Adaptive Metascheduler _"
        print "_     (c) Hilary Oliver, NIWA, 2008-2010      _"
        print "_          cylc is pronounced 'silk'          _"
        print "____________________C_Y_L_C____________________"
        print

        items = self.banner.keys()

        longest_item = items[0]
        for item in items:
            if len(item) > len(longest_item):
                longest_item = item

        template = re.sub( '.', '.', longest_item )

        for item in self.banner.keys():
            print ' o ', re.sub( '^.{' + str(len(item))+ '}', item, template) + '...' + str( self.banner[ item ] )


    def parse_commandline( self ):
        # DERIVED CLASSES PROVIDE:
        #( self.options, self.args ) = self.parser.parse_args()

        # get suite name
        self.suite_name = self.args[0]

        self.username = os.environ['USER']
        self.banner[ 'suite name' ] = self.suite_name

        # get suite hostname
        self.host= socket.getfqdn()
        self.banner[ 'cylc suite host' ] = self.host

        found, port = port_scan.get_port( self.suite_name, self.username, self.host )
        if found and not self.options.practice_mode:
            raise SystemExit( "ERROR: " + self.suite_name + " is already running (port " + str( port ) + ")" )

        # get mode of operation
        if self.options.dummy_mode and self.options.practice_mode:
            parser.error( "Choose ONE of dummy or practice mode")

        if self.options.dummy_mode:
            self.dummy_mode = True
            self.practice = False
            self.banner[ 'mode of operation' ] = 'DUMMY'
        elif self.options.practice_mode:
            self.dummy_mode = True
            self.practice = True
            self.banner[ 'mode of operation' ] = 'PRACTICE DUMMY'
        else:
            self.dummy_mode = False
            self.practice = False
            self.banner[ 'mode of operation' ] = 'REAL'

        self.stop_time = None
        if self.options.stop_time:
            self.stop_time = self.options.stop_time
            if not cycle_time.is_valid( self.stop_time ):
                self.parser.error( "invalid cycle time: " + self.stop_time )

        self.pause_time = None
        if self.options.pause_time:
            self.pause_time = self.options.pause_time
            if not cycle_time.is_valid( self.pause_time ):
                self.parser.error( "invalid cycle time: " + self.pause_time )

        # These options are no longer mutually exclusive.
        #if self.options.include and self.options.exclude:
        #    self.parser.error( '--include and --exclude are mutually exclusive' )

        self.include_tasks = []
        if self.options.include:
            self.include_tasks = self.options.include.split(',')

        self.exclude_tasks = []
        if self.options.exclude:
            self.exclude_tasks = self.options.exclude.split(',')

        self.clock_rate = float( self.options.clock_rate )
        self.clock_offset = float( self.options.clock_offset )
        self.dummy_run_length = float( self.options.dummy_run_length )
        self.failout_task_id = self.options.failout_task_id

    def initialize_graphfile( self ):
        gf_path = self.options.graphfile 
        if not os.path.isabs( gf_path ):
            gf_path = os.environ['HOME'] + '/' + gf_path
        print "Opening dot graph file", gf_path
        default_node_attributes = self.config[ 'default_node_attributes' ]
        default_edge_attributes = self.config[ 'default_edge_attributes' ]
        if self.config[ 'use_node_color_for_edges' ]:
            m = re.search( 'fillcolor *= *(\w+)', default_node_attributes )
            if m:
                nodecolor = m.groups()[0]
                default_edge_attributes += ', color=' + nodecolor

        self.graphfile = open( gf_path, 'w' )
        self.graphfile.write( '''/* This is a "dot" language file generated by cylc.
 * It encodes dependencies resolved during a single run of a 
 * cylc suite, and can be visualized with graphviz:
 *   http://www.graphviz.org
 *   http://www.graphviz.org/doc/
 *
 * Minimal postprocessing example:"
 *  $ dot -Tps  foo.dot -o foo.ps   # ps output"
 *  $ dot -Tsvg foo.dot -o foo.svg  # svg output"
 *
 * Note that nodes in a subgraph with no internal edges all have
 * the same rank (rank determines horizontal placement). To split 
 * the subgraph into several rows you can manually add invisible
 * invisible edges, for example: "node1 -> node2 [color=invis];"
 *
 * When the default node style is "filled" use "unfilled" to get
 * specific nodes that are unfilled (this seems to be undocumented)
 * or just fill with the graph background color.
 *
 * If using dummy mode to generate the graph, specify --clock-offset=0 
 * so that the suite will not simulate catchup to real time operation
 * and nodes will therefore be printed out in a reasonably sensible
 * order as this may affect the final graph layout.
 *
 * Processing this file with the graphviz 'unflatten' command may result
 * in a more pleasing layout.
 *
 * You can use the 'dot -G|N|E' commandline options to experiment with
 * different global settings without editing this dot file directly.
 *
 * Printing large graphs successfully can be problematic. One method 
 * that works on Linux is to generate an svg layout, load into inkscape 
 * and set the page size to A3 under "document properties", save a PDF
 * copy, load that into evince, set A3 again, and 'landscape' if
 * necessary, in "Print Setup", then print the frickin' thing.
 *
 * You can tell dot to split a large layout into a multi-page mosaic
 * that can be pieced together after printing: use the 'page=x,y' and
 * 'size' graph attributes (see dot documentation for details).
 */\n\n''' )
        self.graphfile.write( 'digraph ' + self.suite_name + ' {\n' )
        self.graphfile.write( '    graph [bgcolor=White, fontsize=40, compound=true, \n' )
        self.graphfile.write( '          label="The ' + self.suite_name + ' suite\\n(graph generated by cylc, ' + datetime.datetime.now().strftime( "%Y-%m-%d %H:%M:%S" ) + ')" ];\n' )
        self.graphfile.write( '    node [ ' + default_node_attributes + ' ];\n' )
        self.graphfile.write( '    edge [ ' + default_edge_attributes + ' ];\n' )

    def load_preferences( self ):
        self.rcfile = preferences()

        use = self.rcfile['use quick task elimination'] 
        if use == "False":
            self.use_quick_elim = False
        else:
            self.use_quick_elim = True

        if self.practice:
            self.logging_dir = os.path.join( self.rcfile['logging directory'],    self.suite_name + '-practice' ) 
            state_dump_dir   = os.path.join( self.rcfile['state dump directory'], self.suite_name + '-practice' )
        else:
            self.logging_dir = os.path.join( self.rcfile['logging directory'],    self.suite_name ) 
            state_dump_dir   = os.path.join( self.rcfile['state dump directory'], self.suite_name )

        mkdir_p( self.logging_dir )
        mkdir_p( state_dump_dir )

        self.state_dump_file = os.path.join( state_dump_dir, 'state' )

        self.use_lockserver = False
        self.banner[ 'use lockserver' ] = 'False'
        if self.rcfile['use lockserver']:
            self.banner[ 'use lockserver' ] = 'True'
            self.use_lockserver = True

        if self.dummy_mode:
            # no need to use the lockserver in dummy mode
            self.use_lockserver = False

        if self.use_lockserver:
            # check that a lockserver is running under my username 
            self.lockserver_port = lockserver( self.username, self.host ).ping()

    def get_suite_def_dir( self ):
        # find location of the suite task and config modules
        reg = registrations()
        if reg.is_registered( self.suite_name ):
            self.suite_dir = reg.get( self.suite_name )
        else:
            reg.print_all()
            raise SystemExit( "suite " + self.suite_name + " is not registered!" )

        self.banner[ 'suite definition' ] = self.suite_dir

    def configure_pyro( self ):
        if self.practice:
            # MODIFY SUITE NAME SO WE CAN RUN NEXT TO THE ORIGINAL SUITE.
            suitename = self.suite_name + "-practice"
        else:
            suitename = self.suite_name

        self.pyro = cylc_pyro_server.pyro_server( suitename )
        self.port = self.pyro.get_port()
        self.banner[ 'Pyro port' ] = self.port

    def configure_suite_id( self ):
        self.suite_id = identifier( self.suite_name, self.username )
        self.pyro.connect( self.suite_id, 'cylcid', qualified = False )

    def configure_environment( self ):
        # provide access to the suite scripts and source modules
        # for external processes launched by this program.

        # prepend suite bin to $PATH (prepend in case this is a subsuite!)
        # (NOTE this is still somewhat dangerous: if a subsuite task script
        # that should be executable but isn't has the same filename as a task in
        # the parent suite, the parent file will be found and executed).
        os.environ['PATH'] = self.suite_dir + '/bin:' + os.environ['PATH'] 

    def load_suite_config( self ):
        # TO DO: environment vars COULD GO STRAIGHT TO JOB_SUBMIT
        # ENVIRONMENT (NOT NEEDED IN CONFIG?)

        # import suite-specific cylc modules now
        from config import config 

        # initial global environment
        self.globalenv = OrderedDict()
        self.globalenv[ 'CYLC_MODE' ] = 'scheduler'
        self.globalenv[ 'CYLC_SUITE_HOST' ] =  str( self.host )
        self.globalenv[ 'CYLC_SUITE_PORT' ] =  self.pyro.get_port()
        self.globalenv[ 'CYLC_DIR' ] = os.environ[ 'CYLC_DIR' ]
        self.globalenv[ 'CYLC_SUITE_DIR' ] = self.suite_dir
        self.globalenv[ 'CYLC_SUITE_NAME' ] = self.suite_name
        self.globalenv[ 'CYLC_SUITE_OWNER' ] = self.username
        self.globalenv[ 'CYLC_USE_LOCKSERVER' ] = str( self.use_lockserver )

        # load suite configuration--------------------------------------------
        self.config = config( os.path.join( self.suite_dir, 'suite.rc' ))
        if self.options.debug:
            self.logging_level = logging.DEBUG
        else:
            self.logging_level = self.config.get_logging_level()

        ##### TO DO: self.config.check_task_groups()
        for var in self.config['environment']:
            self.globalenv[ var ] = self.config['environment'][var]

        if self.dummy_mode:
            if self.failout_task_id:
                print "SETTING A FAILOUT TASK: " + self.failout_task_id
                # now done below in configure_job_submission()

            print "SETTING DUMMY TASK RUN LENGTH: " + str( self.dummy_run_length ) + " dummy clock minutes"
            dummy_seconds = self.dummy_run_length * 60
            real_seconds = dummy_seconds * self.clock_rate / 3600.0
            self.globalenv['CYLC_DUMMY_SLEEP'] = real_seconds

        self.exclusive_suite_lock = not self.config[ 'allow multiple simultaneous suite instances' ]

    def back_up_statedump_file( self ):
       # back up the configured state dump (i.e. the one that will be used
       # by the suite unless in practice mode, but not necessarily the
       # initial one). 
       if os.path.exists( self.state_dump_file ):
           backup = self.state_dump_file + '.' + datetime.datetime.now().isoformat()
           print "Backing up the state dump file:"
           print "  " + self.state_dump_file + " --> " + backup
           try:
               shutil.copyfile( self.state_dump_file, backup )
           except:
               raise SystemExit( "ERROR: State dump file copy failed" )

    def configure_dummy_mode_clock( self ):
        # suite clock for accelerated time in dummy mode
        self.clock = accelerated_clock.clock( 
                int(self.clock_rate),
                int(self.clock_offset),
                self.dummy_mode ) 

        self.pyro.connect( self.clock, 'clock' )

    def configure_suite_state_summary( self ):
        # remotely accessible suite state summary
        self.suite_state = state_summary.state_summary( self.config, self.dummy_mode )
        self.pyro.connect( self.suite_state, 'state_summary')

    def configure_dead_letter_box( self ):
        # NOT USED
        # dead letter box for remote use
        self.dead_letter_box = dead_letter.letter_box()
        self.pyro.connect( self.dead_letter_box, 'dead_letter_box')

    def configure_job_submission( self ):
        job_submit.dummy_mode = self.dummy_mode
        job_submit.global_env = self.globalenv
        job_submit.joblog_dir = self.config[ 'job submission log directory' ]
        if self.dummy_mode and self.failout_task_id:
            job_submit.failout_id = self.failout_task_id

    def configure_remote_switch( self ):
        # remote control switch
        import remote_switch
        self.remote = remote_switch.remote_switch( self.config, self.clock, self.suite_dir, self.username, self.pool, self.failout_task_id )
        self.pyro.connect( self.remote, 'remote' )

    def create_task_pool( self ):
        self.pool = None
        # OVERRIDE IN DERIVED CLASSES

    def configure( self ):
        self.load_preferences()
        self.get_suite_def_dir()
        self.configure_pyro()
        self.configure_suite_id()
        self.configure_environment()
        self.configure_dummy_mode_clock()
        self.load_suite_config()
        if self.options.graphfile:
            self.initialize_graphfile()
        else:
            self.graphfile = None
        self.configure_suite_state_summary()
        self.configure_job_submission()

        # required before remote switch
        self.create_task_pool()

        self.configure_remote_switch()

        self.print_banner()
        #self.config.dump()

    def run( self ):
        if self.use_lockserver:
            if self.practice:
                suitename = self.suite_name + '-practice'
            else:
                suitename = self.suite_name

            # request suite access from the lock server
            if suite_lock( suitename, self.suite_dir, self.username, self.host, self.lockserver_port, 'scheduler' ).request_suite_access( self.exclusive_suite_lock ):
               self.lock_acquired = True
            else:
               raise SystemExit( "Failed to acquire a suite lock" )

        if not self.practice:
            self.back_up_statedump_file()

        # logger is now created and pimped
        log = logging.getLogger( 'main' )

        if self.pause_time:
            # TO DO: HANDLE STOP AND PAUSE TIMES THE SAME WAY?
            self.pool.set_suite_hold( self.pause_time )

        print "\nSTARTING\n"

        while True: # MAIN LOOP

            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.

            if self.process_tasks():
                #print "ENTERING MAIN LOOP"
                if self.options.timing:
                    main_loop_start_time = datetime.datetime.now()

                self.pool.negotiate()
                self.pool.run_tasks()
                self.pool.cleanup()
                # spawn after cleanup to avoid unspawned stall at max runahead.
                self.pool.spawn()
                self.pool.dump_state()

                self.suite_state.update( self.pool.tasks, self.clock, \
                        self.pool.paused(), self.pool.will_pause_at(), \
                        self.remote.halt, self.pool.will_stop_at() )

                if self.options.timing:
                    delta = datetime.datetime.now() - main_loop_start_time
                    seconds = delta.seconds + float(delta.microseconds)/10**6
                    print "MAIN LOOP TIME TAKEN:", seconds, "seconds"

            if self.pool.all_tasks_finished():
                log.critical( "ALL TASKS FINISHED" )
                break

            if self.remote.halt_now or self.remote.halt and self.pool.no_tasks_running():
                log.critical( "ALL RUNNING TASKS FINISHED" )
                break

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

        print ""
        print "STOPPING"
        self.cleanup()

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
            
        if self.pool.waiting_contact_task_ready( self.clock.get_datetime() ):
            # This method actually returns True if ANY task is ready to run,
            # not just contact tasks. However, this should not be a problem.
            # For a contact task, this means the contact time is up AND
            # any prerequisites are satisfied, so it can't result in
            # multiple passes through the main loop.

            # cause one pass through the main loop
            answer = True

        return answer


    def cleanup( self ):

        # close graphfile, if it has been opened
        try:
            self.graphfile.write( '}\n' )
        except:
            pass
        else:
            print "Closing graphfile"
            self.graphfile.close()

        if self.pyro:
            self.pyro.shutdown()

        if self.use_lockserver:
            # do this last
            if self.practice:
                suitename = self.suite_name + '-practice'
            else:
                suitename = self.suite_name

            if self.lock_acquired:
                print "Releasing suite lock"
                lock = suite_lock( suitename, self.suite_dir, self.username, self.host, self.lockserver_port, 'scheduler' )
                if not lock.release_suite_access():
                    print >> sys.stderr, 'failed to release suite!'

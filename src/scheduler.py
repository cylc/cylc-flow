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

from preferences import prefs
import cycle_time
import cylc_pyro_server
import dead_letter
import state_summary
import accelerated_clock 
from job_submit import job_submit
from registration import registrations
from system_lock import system_lock
from life import minimal

import task     # loads task_classes

class scheduler:

    def __init__( self ):
        self.banner = {}
        self.pyro = None
        self.use_lockserver = False
        self.lock_acquired = False

        # PROVIDE IN DERIVED CLASSES:
        # self.parser = OptionParser( usage )

        self.parser.set_defaults( pns_host= socket.getfqdn(),
                dummy_mode=False, practice_mode=False,
                include=None, exclude=None, debug=False,
                clock_rate=10, clock_offset=24 )

        self.parser.add_option( "--until", 
                help="Shut down after all tasks have PASSED this cycle time.",
                metavar="CYCLE", action="store", dest="stop_time" )

        self.parser.add_option( "--pause",
                help="Refrain from running tasks AFTER this cycle time.",
                metavar="CYCLE", action="store", dest="pause_time" )

        self.parser.add_option( "--exclude",
                help="Comma-separated list of tasks to exclude at startup "
                "(this option has the same effect as deleting tasks from "
                "task_list.py in the configured system definition directory).",
                metavar="LIST", action="store", dest='exclude' )

        self.parser.add_option( "--include",
                help="Comma-separated list of tasks to include at startup "
                "(this option has the same effect as deleting all *other* tasks "
                "from task_list.py in the configured system definition directory).",
                metavar="LIST", action="store", dest='include' )

        self.parser.add_option( "--host",
                help="Pyro Nameserver host (defaults to local host name).",
                metavar="HOSTNAME", action="store", dest="pns_host" )

        self.parser.add_option( "-d", "--dummy-mode",
                help="Replace each task with a program that masquerades "
                "as the the real thing, and run the system on an accelerated clock.",
                action="store_true", dest="dummy_mode" )

        self.parser.add_option( "-p", "--practice-mode",
                help="Clone an existing system in dummy mode using new state "
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

        self.parser.add_option( "--fail-out", help=\
                "(DUMMY MODE) get task NAME at cycle time CYCLE to report failure "
                "and then abort. Use this to test failure and recovery scenarios.",
                metavar="NAME%CYCLE", action="store", dest="failout_task_id" )

        self.parser.add_option( "--dummy-task-run-length", help=\
                "(DUMMY MODE) change the length of run time, relative to the dummy "
                "mode clock, of each running task. The default is 20 minutes.",
                metavar="MINUTES", action="store", dest="dummy_task_run_length" )

        self.parser.add_option( "--traceback", help=\
                "Print the full exception traceback in case of error.",
                action="store_true", dest="debug" )

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

        # get system name
        self.system_name = self.args[0]
        self.username = os.environ['USER']
        self.banner[ 'system name' ] = self.system_name

        # get Pyro nameserver hostname
        if not self.options.pns_host:
            # (this won't happen; defaults to local hostname)
            self.parser.error( "Required: Pyro nameserver hostname" )
        else:
            self.pns_host = self.options.pns_host
            self.banner[ 'Pyro nameserver host' ] = self.pns_host

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

        if self.options.include and self.options.exclude:
            self.parser.error( '--include and --exclude are mutually exclusive' )

        self.include_tasks = []
        if self.options.include:
            self.include_tasks = self.options.include.split(',')

        self.exclude_tasks = []
        if self.options.exclude:
            self.exclude_tasks = self.options.exclude.split(',')

        self.clock_rate = self.options.clock_rate
        self.clock_offset = self.options.clock_offset
        self.failout_task_id = self.options.failout_task_id
        self.dummy_task_run_length = self.options.dummy_task_run_length

    def load_preferences( self ):
        self.rcfile = prefs()

        use = self.rcfile.get( 'cylc', 'use quick task elimination') 
        if use == "False":
            self.use_quick_elim = False
        else:
            self.use_quick_elim = True

        self.logging_dir = self.rcfile.get_system_logging_dir( self.system_name, self.practice ) 
        self.logging_level = self.rcfile.get_logging_level()
        state_dump_dir = self.rcfile.get_system_statedump_dir( self.system_name , self.practice )
        self.state_dump_file = os.path.join( state_dump_dir, 'state' )

        self.use_lockserver = False
        self.banner[ 'use lockserver' ] = 'False'
        if self.rcfile.get( 'cylc', 'use lockserver' ) == 'True':
            self.banner[ 'use lockserver' ] = 'True'
            self.use_lockserver = True

    def get_system_def_dir( self ):
        # find location of the system task and config modules
        reg = registrations()
        if reg.is_registered( self.system_name ):
            self.system_dir = reg.get( self.system_name )
        else:
            reg.print_all()
            raise SystemExit( "System " + self.system_name + " is not registered!" )

        self.banner[ 'system definition' ] = self.system_dir

    def configure_pyro( self ):
        if self.practice:
            # MODIFY GROUPNAME SO WE CAN RUN NEXT TO THE ORIGINAL SYSTEM.
            sysname = self.system_name + "-practice"
        else:
            sysname = self.system_name

        self.pyro = cylc_pyro_server.pyrex( self.pns_host, sysname )

        self.banner[ 'Pyro nameserver group' ] = self.pyro.get_groupname()

    def configure_lifecheck( self ):
        self.lifecheck = minimal()
        self.pyro.connect( self.lifecheck, 'minimal' )

    def configure_environment( self ):
        # provide access to the system scripts and source modules
        # for external processes launched by this program.

        # prepend system scripts to $PATH (prepend in case this is a subsystem!)
        # (NOTE this is still somewhat dangerous: if a subsystem task script
        # that should be executable but isn't has the same filename as a task in
        # the parent system, the parent file will be found and executed).
        os.environ['PATH'] = self.system_dir + '/scripts:' + os.environ['PATH'] 
        # prepend add system Python modules to $PYTHONPATH (prepend, as above)
        os.environ['PYTHONPATH'] = self.system_dir + ':' + os.environ['PYTHONPATH']

        # provide access to the system source modules for THIS program---------
        # prepend to the module search path in case this is a subsystem
        sys.path.insert(0, os.path.join( self.system_dir, 'tasks' ))
        sys.path.insert(0, self.system_dir )

    def load_system_config( self ):
        # TO DO: PUTENV STUFF BELOW COULD GO STRAIGHT TO JOB_SUBMIT
        # ENVIRONMENT (NOT NEEDED IN CONFIG?)

        # import system-specific cylc modules now
        from system_config import system_config 

        # load system configuration
        self.config = system_config( self.system_name )

        self.config.check_task_groups()
        self.config.job_submit_config( self.dummy_mode )

        # load some command dynamic stuff into config module, for easy handling.
        ####self.config.put( 'daemon', self.pyro_daemon )
        self.config.put( 'clock', self.clock )
        self.config.put( 'logging_dir', self.logging_dir )  # cylc view gets this from state_summary

        # set global (all tasks) environment variables-------------------------
        self.config.put_env( 'CYLC_MODE', 'scheduler' )
        self.config.put_env( 'CYLC_NS_HOST',  str( self.pns_host ) )  # may be an IP number
        self.config.put_env( 'CYLC_NS_GROUP',  self.pyro.get_groupname() )
        self.config.put_env( 'CYLC_DIR', os.environ[ 'CYLC_DIR' ] )
        self.config.put_env( 'CYLC_SYSTEM_DIR', self.system_dir )
        self.config.put_env( 'CYLC_SYSTEM_NAME', self.system_name )
        self.config.put_env( 'CYLC_USE_LOCKSERVER', str( self.use_lockserver) )
        if self.dummy_mode:
            self.config.put_env( 'CYLC_CLOCK_RATE', str( self.clock_rate ) )
            # communicate failout_task_id to the dummy task program
            if self.failout_task_id:
                print "SETTING FAILOUT: " + self.failout_task_id
                self.config.put_env( 'CYLC_FAILOUT_ID', self.failout_task_id )
            if self.dummy_task_run_length:
                print "SETTING DUMMY TASK RUN LENGTH: " + self.dummy_task_run_length
                self.config.put_env( 'CYLC_DUMMY_TASK_RUN_LENGTH', self.dummy_task_run_length )

        self.config.check_environment()

        self.exclusive_system_lock = not self.config.get( 'allow_simultaneous_system_instances' )

    def back_up_statedump_file( self ):
       # back up the configured state dump (i.e. the one that will be used
       # by the system unless in practice mode, but not necessarily the
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
        # system clock for accelerated time in dummy mode
        self.clock = accelerated_clock.clock( 
                int(self.clock_rate),
                int(self.clock_offset),
                self.dummy_mode ) 

        self.pyro.connect( self.clock, 'clock' )

    def configure_system_state_summary( self ):
        # remotely accessible system state summary
        self.system_state = state_summary.state_summary( self.config, self.dummy_mode )
        self.pyro.connect( self.system_state, 'state_summary')

    def configure_dead_letter_box( self ):
        # NOT USED
        # dead letter box for remote use
        self.dead_letter_box = dead_letter.letter_box()
        self.pyro.connect( self.dead_letter_box, 'dead_letter_box')

    def configure_job_submission( self ):
        job_submit.dummy_mode = self.dummy_mode
        job_submit.global_env = self.config.get( 'environment' )

    def configure_remote_switch( self ):
        # remote control switch
        import remote_switch
        self.remote = remote_switch.remote_switch( self.config, self.pool, self.failout_task_id )
        self.pyro.connect( self.remote, 'remote' )

    def create_task_pool( self ):
        self.pool = None
        # OVERRIDE IN DERIVED CLASSES

    def configure( self ):
        self.load_preferences()
        self.get_system_def_dir()
        self.configure_pyro()
        self.configure_lifecheck()
        self.configure_environment()
        self.configure_dummy_mode_clock()
        self.load_system_config()
        self.configure_system_state_summary()
        self.configure_job_submission()

        # required before remote switch
        self.create_task_pool()

        self.configure_remote_switch()

        self.print_banner()
        self.config.dump()

    def run( self ):

        if self.use_lockserver:
            if self.practice:
                sysname = self.system_name + '-practice'
            else:
                sysname = self.system_name

            # request system access from the lock server
            lock = system_lock( self.pns_host, self.username,
                    sysname, self.system_dir, 'scheduler' )
            if not lock.request_system_access( self.exclusive_system_lock ):
                raise SystemExit( 'locked out!' )
            else:
                self.lock_acquired = True

        if not self.practice:
            self.back_up_statedump_file()

        # logger is now created and pimped
        log = logging.getLogger( 'main' )

        if self.pause_time:
            # TO DO: HANDLE STOP AND PAUSE TIMES THE SAME WAY?
            self.pool.set_system_hold( self.pause_time )

        print "\nSTARTING\n"

        #count = 0
        task.state_changed = True

        while True: # MAIN LOOP

            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.

            if task.state_changed or \
                    self.remote.process_tasks or \
                    self.pool.waiting_contact_task_ready( self.clock.get_datetime() ):

                self.pool.negotiate()
                self.pool.run_tasks()
                self.pool.cleanup()
                # spawn after cleanup in case the system stalled
                # unspawned at max runahead.
                self.pool.spawn()
                self.pool.dump_state()

                self.system_state.update( self.pool.tasks, self.clock, \
                        self.pool.paused(), self.pool.will_pause_at(), \
                        self.remote.halt, self.pool.will_stop_at() )

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
            #--

            # incoming task messages set this to True
            task.state_changed = False
            self.remote.process_tasks = False
            # handle all remote calls
            self.pyro.handleRequests( timeout=None )

        # END MAIN LOOP

        print ""
        print "STOPPING"
        self.cleanup()

    def cleanup( self ):
        if self.pyro:
            self.pyro.shutdown( True )

        if self.use_lockserver:
            # do this last
            if self.practice:
                sysname = self.system_name + '-practice'
            else:
                sysname = self.system_name

            if self.lock_acquired:
                print "Releasing system lock"
                lock = system_lock( self.pns_host, self.username,
                        sysname, self.system_dir, 'scheduler' )
                if not lock.release_system_access():
                    print >> sys.stderr, 'failed to release system!'

# to simulate the effect on monitoring etc. of long task processing time
# (many many many tasks...), put this in the task processing loop:
#if count % 50 == 0:
#    # every 50th time, sleep for 30s
#    print 'SLEEPING 30s!'
#    time.sleep(30)

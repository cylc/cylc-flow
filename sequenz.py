#!/usr/bin/python

import dummy_mode_clock 
from master_control import main_switch
import pyro_ns_naming
import pyro_setup
import pimp_my_logger
import task_base
import task_manager
import dead_letter
import config

import logging
import sys, os, re

global pyro_daemon

def print_banner():
    print "__________________________________________________________"
    print
    print "      . EcoConnect Dynamic Sequencing Controller ."
    print
    print "      .         Hilary Oliver, NIWA, 2008         ."
    print "              See repository documentation"
    print "      .    Pyro nameserver required: 'pyro-ns'    ."
    print "__________________________________________________________"

def clean_shutdown( reason ):
    global pyro_daemon
    log = logging.getLogger( 'main' )
    log.critical( 'System Halt: ' + reason )
    pyro_daemon.shutdown( True ) 
    sys.exit(0)

def usage():
    print "sequenz [-r]"
    print "Options:"
    print "  + most inputs should be configured in config.py"
    print "  + [-r] restart from state dump file (this overrides"
    print "    the configured start time and task list)."

def main( argv ):
    if len( argv ) - 1 > 1:
        usage()
        sys.exit(1)

    restart = False
    if len( argv ) -1 == 1 and argv[1] == '-r':
        restart = True

    print_banner()

    # create the Pyro daemon
    global pyro_daemon
    pyro_daemon = pyro_setup.create_daemon()

    # dummy mode accelerated clock
    if config.dummy_mode:
        dummy_clock = dummy_mode_clock.time_converter( config.start_time, config.dummy_clock_rate, config.dummy_clock_offset ) 
        pyro_daemon.connect( dummy_clock, pyro_ns_naming.name( 'dummy_clock' ) )
    else:
        dummy_clock = None

    print
    print 'Logging to ' + config.logging_dir
    if not os.path.exists( config.logging_dir ):
        os.makedirs( config.logging_dir )

    # top level logging
    log = logging.getLogger( 'main' )
    pimp_my_logger.pimp_it( log, 'main', dummy_clock )

    # remotely accessible control switch
    master = main_switch()
    pyro_daemon.connect( master, pyro_ns_naming.name( 'master' ) )

    # dead letter box for remote use
    dead_letter_box = dead_letter.letter_box()
    pyro_daemon.connect( dead_letter_box, pyro_ns_naming.name( 'dead_letter_box' ) )

    # initialize the task pool from general config file or state dump
    pool = task_manager.manager( pyro_daemon, restart, dummy_clock )
    pyro_daemon.connect( pool, pyro_ns_naming.name( 'god' ) )

    print
    print "Beginning task processing now"
    if config.dummy_mode:
        print "      (DUMMY MODE)"
    print
 
    while True: # MAIN LOOP ###################################
        if master.system_halt:
            clean_shutdown( 'remote request' )

        if task_base.state_changed and not master.system_pause:
            # PROCESS ALL TASKS whenever one changes state as
            # a result of a remote task message coming in.

            pool.regenerate()

            pool.interact()

            pool.run_if_ready()

            pool.dump_state()

            if pool.all_finished():
                clean_shutdown( 'ALL TASKS FINISHED' )

            pool.kill_spent_tasks()

            pool.kill_lame_ducks()

        # PYRO REQUEST HANDLING; returns after one or more remote
        # method invocations are processed (these are not just task
        # messages, hence the use of task_base.state_changed above).

        task_base.state_changed = False
        pyro_daemon.handleRequests( timeout = None )

    ############################################################

if __name__ == "__main__":
    main( sys.argv )

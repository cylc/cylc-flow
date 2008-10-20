#!/usr/bin/python

import dummy_mode_clock 
from master_control import main_switch
import pyro_ns_naming
import pyro_setup
import logging_setup
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
    print "      . EcoConnect Implicit Sequencing Controller ."
    print
    print "      .         Hilary Oliver, NIWA, 2008         ."
    print "              See repository documentation"
    print "      .    Pyro nameserver required: 'pyro-ns'    ."
    print "__________________________________________________________"


def usage():
    print "ecocontroller [-r]"
    print "Options:"
    print "  + most inputs should be configured in config.py"
    print "  + [-r] restart from state dump file (this overrides"
    print "    the configured start time and task list)."


def clean_shutdown( reason ):
    global pyro_daemon
    log = logging.getLogger( 'main' )
    log.critical( 'System Halt: ' + reason )
    pyro_daemon.shutdown( True ) 
    sys.exit(0)


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

    # task-type based hierarchical logging
    logging_setup.create_logs( dummy_clock )
    log = logging.getLogger( 'main' )

    # remotely accessible control switch
    master = main_switch()
    pyro_daemon.connect( master, pyro_ns_naming.name( 'master' ) )

    # dead letter box for remote use
    dead_letter_box = dead_letter.letter_box()
    pyro_daemon.connect( dead_letter_box, pyro_ns_naming.name( 'dead_letter_box' ) )

    # initialize the task pool, as configured or from the state dump
    if restart:
        print
        print 'Starting from state dump file ' + config.state_dump_file
        log.info( 'starting from state dump file ' + config.state_dump_file )

    else:
        print
        print 'Initial reference time ' + config.start_time
        log.info( 'initial reference time ' + config.start_time )

    stop_time = None
    if config.stop_time:
        print 'Final reference time ' + config.stop_time
        log.info( 'final reference time ' + config.stop_time )
        stop_time = config.stop_time
    
    pool = task_manager.manager( pyro_daemon, restart, config.task_list, config.start_time, stop_time )
    pyro_daemon.connect( pool, pyro_ns_naming.name( 'god' ) )

    print
    print "Beginning task processing now"
    if config.dummy_mode:
        print "      (DUMMY MODE)"
    print
 
    while True: # MAIN LOOP ################################
        if master.system_halt:
            clean_shutdown( 'remote request' )

        # TASK PROCESSING, each time a task message comes in
        if task_base.state_changed and not master.system_pause:

            pool.create_tasks()

            pool.interact()

            pool.run_if_ready()

            pool.dump_state()

            if pool.all_finished():
                clean_shutdown( 'ALL TASKS FINISHED' )

            pool.kill_spent_tasks()

            pool.kill_lame_ducks()

        task_base.state_changed = False
        # PYRO REQUEST HANDLING, returns after one or
        # more remote method invocations is processed
        pyro_daemon.handleRequests( timeout = None )
    #########################################################


if __name__ == "__main__":
    main( sys.argv )

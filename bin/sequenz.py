#!/usr/bin/python

# USE $PYTHONPATH IN YOUR ENVIRONMENT TO MAKE AVAILABLE:
# 1/ sequenz 'src' module directory
# 2/ user config module (for user_config.py and task_classes.py)

import dummy_mode_clock 
import pyro_ns_naming
import pimp_my_logger
import task_manager
import dead_letter
import pyro_setup
import task_base
import logging
import profile
import config
import remote
import sys
import os
import re

# auto-replace with version tag at build/install:
sequenz_version = "foo-bar-baz";

def usage():
    print "sequenz [-r]"
    print "Options:"
    print "  + [-r] restart from state dump file (overriding"
    print "         the configured start time and task list)."

def pyro_connect( object, name ):
    global pyro_nameserver_group
    global pyro_daemon
    object_id = pyro_ns_naming.name( name, pyro_nameserver_group )
    pyro_daemon.connect( object, object_id )

def clean_shutdown( pyro_daemon, reason ):
    log = logging.getLogger( 'main' )
    log.critical( 'System Halt: ' + reason )
    pyro_daemon.shutdown( True ) 


# MAIN PROGRAM
#---
def main( argv ):

    if len( argv ) > 2:
        usage()
        sys.exit(1)

    if len( argv ) == 2 and argv[1] == '-r':
        restart = True
    else:
        restart = False

    print "__________________________________________________________"
    print
    print "      .       Sequenz Dynamic Metascheduler       ."
    print "version: " + sequenz_version
    print "      .         Hilary Oliver, NIWA, 2008         ."
    print "              See repository documentation"
    print "      .    Pyro nameserver required: 'pyro-ns'    ."
    print "__________________________________________________________"

    # load system config defaults
    system_config = config.config()
    system_config.load()

    # pyro nameserver group name for the configured task set
    global pyro_nameserver_group
    pyro_nameserver_group = system_config.get( 'pyro_ns_group' )

    # create the Pyro daemon
    global pyro_daemon
    pyro_daemon = pyro_setup.create_daemon( pyro_nameserver_group )

    # dummy mode accelerated clock
    if system_config.get('dummy_mode'):
        dummy_clock = dummy_mode_clock.time_converter( system_config.get('start_time'), 
                                                       system_config.get('dummy_clock_rate'), 
                                                       system_config.get('dummy_clock_offset') ) 
        pyro_connect( dummy_clock, 'dummy_clock' )
    else:
        dummy_clock = None

    # create logging dirs
    if not os.path.exists( system_config.get('logging_dir') ):
       os.makedirs( system_config.get('logging_dir') )

    # top level logging
    log = logging.getLogger( 'main' )
    pimp_my_logger.pimp_it( log, 'main', system_config, dummy_clock )

    # remote control switch
    remote_switch = remote.switch()
    pyro_connect( remote_switch, 'remote_switch' )

    # remotely accessible system state summary
    state_summary = remote.state_summary()
    pyro_connect( state_summary, 'state_summary' )

    # dead letter box for remote use
    dead_letter_box = dead_letter.letter_box()
    pyro_connect( dead_letter_box, 'dead_letter_box' )

    # initialize the task task_pool from general config file or state dump
    task_pool = task_manager.task_manager( system_config, pyro_daemon, restart, dummy_clock )

    print "\nBeginning task processing now\n"

    while True: # MAIN LOOP

        if remote_switch.system_halt:
            clean_shutdown( pyro_daemon, 'remote request' )
	    return

        if task_base.state_changed and not remote_switch.system_pause:
            # PROCESS ALL TASKS whenever one has changed state
            # as a result of a remote task message coming in: 
            # interact OR negotiate with a requisite broker,
            # then run, create new, and kill spent tasks
            #---
            task_pool.regenerate( system_config )

            if system_config.get('use_broker'):
                task_pool.negotiate()
            else:
                task_pool.interact()

            task_pool.run_if_ready()

            task_pool.kill_spent_tasks( system_config )

            task_pool.kill_lame_tasks( system_config )

            task_pool.dump_state( system_config )

            state_summary.update( task_pool.tasks )

            if task_pool.all_finished():
                clean_shutdown( pyro_daemon, "ALL TASKS FINISHED" )
                return

        # REMOTE METHOD HANDLING; with no timeout and single-
        # threaded pyro, handleRequests() returns after one or
        # more remote method invocations are processed (these 
        # are not just task messages, hence the use of the
        # state_changed variable above).
        #---
        task_base.state_changed = False
        pyro_daemon.handleRequests( timeout = None )

     # END MAIN LOOP

if __name__ == "__main__":
    
    if False:
	# Do this to get performance profiling information
	# This method has a big performance hit itself, so
	# maybe there is a better way to do it?!)
        profile.run( 'main( sys.argv )' )
    else:
    	main( sys.argv )

#!/usr/bin/python

# USE $PYTHONPATH IN YOUR ENVIRONMENT TO MAKE AVAILABLE:
# 1/ sequenz 'src' module directory
# 2/ user config module (for user_config.py and task_classes.py)

import re
import os
import sys
import task
import pyrex
import remote
import config
import profile
import manager
import logging
import execution
import dead_letter
import pimp_my_logger
import dummy_mode_clock 

# auto-replace with version tag at build/install:
sequenz_version = "foo-bar-baz";

def usage():
    print "sequenz [-r]"
    print "Options:"
    print "  + [-r] restart from state dump file (overriding"
    print "         the configured start time and task list)."

def clean_shutdown( pyro, reason ):
    log = logging.getLogger( 'main' )
    log.critical( 'System Halt: ' + reason )
    pyro.shutdown( True ) 

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

    # external task launcher
    launcher = execution.launcher( system_config )

    # configure my pyro helper
    pyro = pyrex.pyrex( system_config.get( 'pyro_ns_group' ))

    # dummy mode accelerated clock
    if system_config.get('dummy_mode'):
        dummy_clock = dummy_mode_clock.time_converter( system_config.get('start_time'), 
                                                       system_config.get('dummy_clock_rate'), 
                                                       system_config.get('dummy_clock_offset') ) 
        pyro.connect( dummy_clock, 'dummy_clock' )
    else:
        dummy_clock = None

    print "CREATING MAIN LOG......."
    # create logging dirs
    if not os.path.exists( system_config.get('logging_dir') ):
       os.makedirs( system_config.get('logging_dir') )

    # top level logging
    log = logging.getLogger( 'main' )
    pimp_my_logger.pimp_it( log, 'main', system_config, dummy_clock )

    # remote control switch
    remote_switch = remote.switch()
    pyro.connect( remote_switch, 'remote_switch' )

    # remotely accessible system state summary
    state_summary = remote.state_summary()
    pyro.connect( state_summary, 'state_summary' )

    # dead letter box for remote use
    dead_letter_box = dead_letter.letter_box()
    pyro.connect( dead_letter_box, 'dead_letter_box' )

    # initialize the task manager from general config file or state dump
    god = manager.manager( system_config, pyro, restart, dummy_clock )

    print "\nBeginning task processing now\n"

    while True: # MAIN LOOP

        if remote_switch.system_halt:
            clean_shutdown( pyro, 'remote request' )
	    return

        if task.state_changed and not remote_switch.system_pause:
            # PROCESS ALL TASKS whenever one has changed state
            # as a result of a remote task message coming in: 
            # interact OR negotiate with a requisite broker,
            # then run, create new, and kill spent tasks
            #---

            god.regenerate_tasks( system_config )

            if system_config.get('use_broker'):
                god.negotiate()
            else:
                god.interact()

            god.run_tasks( launcher )

            god.kill_spent_tasks( system_config )

            god.kill_lame_tasks( system_config )

            god.dump_state( system_config )

            state_summary.update( god.tasks )

            if god.all_finished():
                clean_shutdown( pyro, "ALL TASKS FINISHED" )
                return

        # REMOTE METHOD HANDLING; with no timeout and single-
        # threaded pyro, handleRequests() returns after one or
        # more remote method invocations are processed (these 
        # are not just task messages, hence the use of the
        # state_changed variable above).
        #---
        task.state_changed = False
        pyro.handleRequests( timeout = None )

     # END MAIN LOOP

if __name__ == "__main__":
    
    if False:
	# Do this to get performance profiling information
	# This method has a big performance hit itself, so
	# maybe there is a better way to do it?!)
        profile.run( 'main( sys.argv )' )
    else:
    	main( sys.argv )

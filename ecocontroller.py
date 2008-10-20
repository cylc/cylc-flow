#!/usr/bin/python

from dummy_clock import *
from master_control import main_switch
from pyro_ns_naming import *
from setup_pyro import *
from task_definitions import task_base 
from task_pool import *
from dead_letter_box import *
from setup_logging import *
import config

import logging
import sys, os, re

def clean_shutdown( reason ):
    log = logging.getLogger( 'main' )
    log.critical( 'System Halt: ' + reason )
    pyro_daemon.shutdown( True ) 
    sys.exit(0)

print "__________________________________________________________"
print
print "      . EcoConnect Implicit Sequencing Controller ."
print
print "      .         Hilary Oliver, NIWA, 2008         ."
print "              See repository documentation"
print "      .    Pyro nameserver required: 'pyro-ns'    ."
print "__________________________________________________________"

# create the Pyro daemon
pyro_daemon = setup_pyro()

# dummy mode accelerated clock
if config.dummy_mode:
    dummy_clock = dummy_clock( config.start_time, config.dummy_clock_rate, config.dummy_clock_offset ) 
    pyro_daemon.connect( dummy_clock, pyro_ns_name( 'dummy_clock' ) )
else:
    dummy_clock = None

# task type based hierarchical logging
setup_logging( dummy_clock )
log = logging.getLogger( 'main' )

# remotely accessible control switch
master = main_switch()
pyro_daemon.connect( master, pyro_ns_name( 'master' ) )

# dead letter box for remote use
dead_letter_box = dead_letter_box()
pyro_daemon.connect( dead_letter_box, pyro_ns_name( 'dead_letter_box' ) )

print
print 'initial reference time ' + config.start_time
log.info( 'initial reference time ' + config.start_time )

if config.stop_time:
    print 'final reference time ' + config.stop_time
    log.info( 'final reference time ' + config.stop_time )

print
print "beginning task processing now"
if config.dummy_mode:
    print "      (DUMMY MODE)"
print
 
# initialize the task pool with the configured task list
task_pool = task_pool( config.task_list, pyro_daemon )
pyro_daemon.connect( task_pool, pyro_ns_name( 'god' ) )

while True: # MAIN LOOP ################################

    if master.system_halt:
        clean_shutdown( 'remote request' )

    # TASK PROCESSING, each time a task message comes in
    if task_base.state_changed and not master.system_pause:

        task_pool.spawn_new_tasks()

        task_pool.interact()

        task_pool.run_if_ready()

        if task_pool.all_finished():
            clean_shutdown( 'ALL TASKS FINISHED' )

        task_pool.kill_spent_tasks()

        task_pool.kill_lame_ducks()

        task_pool.dump_state()

    task_base.state_changed = False
    # PYRO REQUEST HANDLING, returns after one or
    # more remote method invocations is processed
    pyro_daemon.handleRequests( timeout = None )

#########################################################

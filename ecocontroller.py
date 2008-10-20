#!/usr/bin/python

from dummy_clock import *
from control import *
from pyro_ns_naming import *
from setup_pyro import *
from task_definitions import task_base 
from task_pool import *
from dead_letter_box import *
from setup_logging import *
import config

import logging
import sys, os, re
import pdb

print "__________________________________________________________"
print
print "      . EcoConnect Implicit Sequencing Controller ."
print 
print "              Hilary Oliver, NIWA, 2008"
print "             See repository documentation"
print "          Pyro nameserver required: 'pyro-ns'"
print "__________________________________________________________"

# THINGS THAT MUST BE DEFINED IN CONFIG.PY:
#  1. start_time ('yyyymmddhh')
#  2. stop_time  ('yyyymmddhh', or None for no stop)
#  3. dummy_mode (dummy out all tasks)
#  4. dummy_clock_rate (seconds per simulated hour) 
#  5. dummy_clock_offset (hours before start_time)
#  6. task_list (tasks out of task_definitions module to run)
#  7. dummy_out (tasks to dummy out even when dummy_mode is False)
#  8. logging_dir (directory under which to put all log files)
#  9. logging_level (logging.INFO or logging.DEBUG)
# 10. pyro_ns_group (must be unique for each running controller)

# Pyro
pyro_daemon = setup_pyro()

# dummy mode accelerated clock
if config.dummy_mode:
    dummy_clock = dummy_clock( config.start_time, config.dummy_clock_rate, config.dummy_clock_offset ) 
    pyro_daemon.connect( dummy_clock, pyro_ns_name( 'dummy_clock' ) )
else:
    dummy_clock = None

# task type based logging hierarchy
setup_logging( dummy_clock )
log = logging.getLogger( 'main' )

# remotely accessible control switches
control = control( pyro_daemon )
pyro_daemon.connect( control, pyro_ns_name( 'control' ) )

# dead letter box
dead_letter_box = dead_letter_box()
pyro_daemon.connect( dead_letter_box, pyro_ns_name( 'dead_letter_box' ) )

print
print 'initial reference time ' + config.start_time
log.info( 'initial reference time ' + config.start_time )

if config.stop_time:
    print 'Final reference time ' + config.stop_time
    log.info( 'final reference time ' + config.stop_time )

print
print "beginning task processing"
if config.dummy_mode:
    print "      (DUMMY MODE)"
print
 
# initialize the task pool with the configured task list
task_pool = task_pool( config.task_list, pyro_daemon )
pyro_daemon.connect( task_pool, pyro_ns_name( 'god' ) )

while True: # MAIN LOOP ################################

    if control.system_halt:
        control.clean_shutdown( 'requested' )

    # TASK PROCESSING, each time a task message comes in
    if task_base.state_changed and not control.system_pause:

        task_pool.spawn_new_tasks()

        task_pool.interact()

        task_pool.run_if_ready()

        if task_pool.all_finished():
            control.clean_shutdown( 'ALL TASKS FINISHED' )

        task_pool.kill_spent_tasks()

        task_pool.kill_lame_ducks()

        task_pool.dump_state()

    task_base.state_changed = False
    # PYRO REQUEST HANDLING, returns after one or
    # more remote method invocations is processed
    pyro_daemon.handleRequests( timeout = None )

#########################################################

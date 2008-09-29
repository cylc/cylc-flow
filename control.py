#!/usr/bin/python

"""
========= ECOCONNECT CONTROLLER WITH IMPLICIT SCHEDULING ===============
                    Hilary Oliver, NIWA, 2008
                   See repository documentation
"""

from task_manager import task_manager
import dclock
import shared

import Pyro.core
import Pyro.naming
import sys

# check command line arguments
n_args = len( sys.argv ) - 1

if n_args < 1 or n_args > 2 :
    print "USAGE:", sys.argv[0], "<REFERENCE_TIME> [<config file>]"
    sys.exit(1)

initial_reference_time = sys.argv[1]
task_config_file = None
if n_args == 2: task_config_file = sys.argv[2]

print
print "__________________________________________________________"
print "      .                                           ."
print "      . EcoConnect Implicit Scheduling Controller ."
print "__________________________________________________________"
print
print "Initial Reference Time " + sys.argv[1] 

if n_args == 1:
    print
    print "No task config file: will run ALL tasks"

if shared.run_mode == 1:
    # dummy mode clock in its own thread
    shared.dummy_clock = dclock.dclock( sys.argv[1] )
    shared.dummy_clock.start()

# initialise the task manager
god = task_manager( initial_reference_time, task_config_file )

# start processing
god.run()

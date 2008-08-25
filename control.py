#!/usr/bin/python

"""
========= ECOCONNECT CONTROLLER WITH IMPLICIT SCHEDULING ===============
                    Hilary Oliver, NIWA, 2008
         See repository documentation for more information.
"""

from task_manager import task_manager
from shared import pyro_daemon, state

import Pyro.core
import Pyro.naming
import threading
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

print
print "Starting Pyro Nameserver ..."

# Start a Pyro nameserver in its own thread
# (alternatively, run the 'pyro-ns' script as a separate process)
print
ns_starter = Pyro.naming.NameServerStarter()
ns_thread = threading.Thread( target = ns_starter.start )
ns_thread.setDaemon(True)
ns_thread.start()
ns_starter.waitUntilStarted(10)
# locate the Pyro nameserver
ns = Pyro.naming.NameServerLocator().getNS()
pyro_daemon.useNameServer(ns)

# connect the system status monitor to the pyro nameserver
uri = pyro_daemon.connect( state, "state" )

# initialise the task manager
god = task_manager( initial_reference_time, task_config_file )

# start processing
god.run()

#!/usr/bin/python

"""
========= ECOCONNECT CONTROLLER WITH IMPLICIT SCHEDULING ===============
                    Hilary Oliver, NIWA, 2008
                   See repository documentation
"""

from task_manager import task_manager
from system_status import system_status
import dclock
import shared
from dead_letter_box import dead_letter_box

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
pyro_nameserver = Pyro.naming.NameServerLocator().getNS()
shared.pyro_daemon = Pyro.core.Daemon()
shared.pyro_daemon.useNameServer(pyro_nameserver)

# connect the system status monitor to the pyro nameserver
shared.state = system_status()
uri = shared.pyro_daemon.connect( shared.state, "state" )

# dead letter box for use by external tasks
dead_letter_box = dead_letter_box()
uri = shared.pyro_daemon.connect( dead_letter_box, "dead_letter_box" )

if shared.run_mode == 1:
    # dummy mode clock in its own thread
    shared.dummy_clock = dclock.dclock( sys.argv[1] )
    shared.dummy_clock.start()

# initialise the task manager and connect to pyro nameserver
god = task_manager( initial_reference_time, task_config_file )
uri = shared.pyro_daemon.connect( god, "god" )

# start processing
god.run()

#!/usr/bin/python

from system_status import system_status
from reference_time import reference_time 
from vtask_config import vtask_config

import Pyro.core
import Pyro.naming
import sys

import threading

"""
========= ECOCONNECT CONTROLLER WITH IMPLICIT SCHEDULING ===============
                    Hilary Oliver, NIWA, 2008
         See repository documentation for more information.
"""


def create_tasks():

    global reference_time
    global task_list
    global god

    task_list = god.create_tasks( reference_time )
    for task in task_list:
        uri = daemon.connect( task, task.identity() )


def process_tasks():

    global reference_time
    global task_list
    global status

    finished = []
    status.reset()

    if len( task_list ) == 0:
        create_tasks()

    if len( task_list ) == 0:
        # still no tasks means we've reached the end
        print "No tasks created for ", reference_time.to_str()
        print "STOPPING NOW"
        sys.exit(0)

    status.update( reference_time.to_str() )

    for task in task_list:
        task.get_satisfaction( task_list )
        task.run_if_satisfied()
        status.update( task.get_status() )
        finished.append( task.finished )

    status.update_finished() 

    if not False in finished:
        reference_time.increment()
        del task_list[:]

    return 1  # required return value for the pyro requestLoop call


#========( MAIN PROGRAM )===============================================

# check command line arguments
n_args = len( sys.argv ) - 1

if n_args < 1 or n_args > 2 :
    print "USAGE:", sys.argv[0], "<REFERENCE_TIME> [<config file>]"
    sys.exit(1)

reference_time = reference_time( sys.argv[1] )

if n_args == 2:
    config_file = sys.argv[2]
else:
    config_file = None

# Start a Pyro nameserver in its own thread
# (alternatively, run the 'pyro-ns' script as a separate process)
ns_starter = Pyro.naming.NameServerStarter()
ns_thread = threading.Thread( target = ns_starter.start )
ns_thread.setDaemon(True)
ns_thread.start()
ns_starter.waitUntilStarted(10)

# locate the Pyro nameserver
daemon = Pyro.core.Daemon()
ns = Pyro.naming.NameServerLocator().getNS()
daemon.useNameServer(ns)

# create a system status monitor and connect it to the pyro nameserver
status = system_status()
uri = daemon.connect( status, "system_status" )

# print startup information
print
print "-----------------------------------"
print "------ EcoConnect Controller ------"
print "follow tasks with system_monitor.py"
print "-----------------------------------"
print
print "Initial Reference Time " + reference_time.to_str()
print
if config_file is None:
    print "No config file, using ALL tasks"
    print

task_list = []

# initialize the task creator 
god = vtask_config( config_file )

# Process once to start any tasks that have no prerequisites
# We need at least one of this to start the system rolling 
# (i.e. the downloader).  Thereafter things only happen only
# when a running task gets a message via pyro). 
process_tasks()

# process tasks again each time a request is handled
daemon.requestLoop( process_tasks )

# NOTE: this seems the easiest way to handle incoming pyro calls
# AND run our task processing at the same time, but I might be 
# using requestLoop's "condition" argument in an unorthodox way.
# See pyro docs, as there are other ways to do this, if necessary.
# E.g. use "handleRequests()" instead of "requestLoop", with a 
# timeout that drops into our task processing loop.

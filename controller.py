#!/usr/bin/python

from system_status import system_status
from time import sleep
from reference_time import reference_time 
from vtasks_dummy import *

import Pyro.core
import Pyro.naming
import os
import sys

"""
========= ECOCONNECT CONTROLLER WITH IMPLICIT SCHEDULING ===============
         See repository documentation for more information.
"""

def create_tasks():
    del task_list[:]
    task_list.append( A( reference_time )) 
    task_list.append( B( reference_time ))
    task_list.append( C( reference_time ))
    task_list.append( D( reference_time )) 

    task_list.append( Z( reference_time )) 

    task_list.append( E( reference_time ))
    task_list.append( F( reference_time ))

    for task in task_list:
        uri = daemon.connect( task, task.identity() )



def process_tasks():
    finished = []
    status.reset()

    status.update( reference_time.to_str() )

    for task in task_list:
        task.get_satisfaction( task_list )
        task.run_if_satisfied()
        status.update( task.get_status() )
        finished.append( task.finished )

    status.update_finished() 

    if not False in finished:
        reference_time.increment()
        print "NEW REFERENCE TIME: " + reference_time.to_str()
        create_tasks()

    return 1


# Start the pyro nameserver before running this program. 
# See http://pyro.sourceforge.net/manual/5-nameserver.html
# for other ways to do this.
daemon = Pyro.core.Daemon()
ns = Pyro.naming.NameServerLocator().getNS()
daemon.useNameServer(ns)

# one command line argument: initial reference time 
if len( sys.argv ) != 2:
    print "USAGE:", sys.argv[0], "<REFERENCE_TIME>"
    sys.exit(1)

reference_time = reference_time( sys.argv[1] )
    
print 
print "*** EcoConnect Controller Task Manager Startup ***"
print "    Initial Reference Time " + reference_time.to_str()
print

# create a system status monitor and connect it to the pyro nameserver
status = system_status()
uri = daemon.connect( status, "system_status" )

# create initial task objects and connect them to the pyro nameserver
task_list = []
create_tasks()

# Process once to start one or more tasks that have no prerequisites
# (otherwise nothing will happen; subsequently things only happen only
# when a running task gets a message via pyro). 
process_tasks()

# process tasks again each time a request is handled
daemon.requestLoop( process_tasks )

# NOTE: this seems the easies way to handle incoming pyro calls
# AND run our task processing at the same time, but I might be 
# using requestLoop's "condition" argument in an unorthodox way.
# See pyro docs, as there are other ways to do this, if necessary.
# E.g. use "handleRequests()" instead of "requestLoop", with a 
# timeout that drops into our task processing loop.

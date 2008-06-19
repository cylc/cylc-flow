#!/usr/bin/python

from vtasks import *
from time import sleep
from reference_time import reference_time 
from ec_globals import dummy_mode

import Pyro.core
import Pyro.naming

"""
Ecoconnect Controller with Implicit Scheduling

This program creates and manages vtask objects, which represent
external ecoconnect tasks (see next para), can launch the external
tasks when certain prerequisite conditions are satisfied, and which
update their internal state to reflect the status of the external task.
Vtasks interact in order to satisfy each other's prerequisites, which
may include conditions such as: 
 * file foo_<reference_time>.nc completed 
 * sub-task foo finished successfully"

A vtask should represent a distinct "schedulable task unit": it can be
[physical model M + all postprocessing for M] or [physical model N] or
[all postprocessing for model P] or [postprocessing for scientific
monitoring of model Q], etc., depending on schedulding requirements.
"""

cycle_time = reference_time( "2008053112" )
    
# Start the pyro nameserver before running this program. There are
# various ways to do this, with various options.  
# See http://pyro.sourceforge.net/manual/5-nameserver.html

daemon = Pyro.core.Daemon()
ns = Pyro.naming.NameServerLocator().getNS()
daemon.useNameServer(ns)


tasks = []
def create_tasks():
    del tasks[:]
    tasks.append( downloader( cycle_time )) # runs immediately
    tasks.append( topnet( cycle_time ))
    tasks.append( ricom( cycle_time ))
    tasks.append( nwp_global( cycle_time ))
    tasks.append( globalwave120( cycle_time ))
    tasks.append( nzwave12( cycle_time ))
    tasks.append( nzlam12( cycle_time ))

    for task in tasks:
        uri = daemon.connect( task, task.identity() )

create_tasks()

while True:
    print " "
    #print "handling requests ..."
    daemon.handleRequests(3.0)
    #print "interacting ..."
    finished = []
    for task in tasks:
        task.get_satisfaction( tasks )
        task.run_if_satisfied()
        finished.append( task.finished )

    #print "checking finished"
    if not False in finished:
        print "all finished for " + cycle_time.to_str()
        cycle_time.increment()
        print "NEW REFERENCE TIME: " + cycle_time.to_str()
        print ""
        create_tasks()

    #print "sleeping 2" 
    sleep(2)

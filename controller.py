#!/usr/bin/python

from vtasks import *
from time import sleep
from reference_time import reference_time 
from ec_globals import dummy_mode

import Pyro.core
import Pyro.naming

"""
========= ECOCONNECT CONTROLLER WITH IMPLICIT SCHEDULING ===============

This program manages VTASK OBJECTS that represent external EcoConnect
tasks (a "task" is any set of processes that, as a group, we want
separate scheduling control over). A vtask has a set of task-specific
prerequisites (e.g. existence of a particular input file) that have to
be satisfied before the external task can run, a set of task-specific
"postrequisites" (e.g.  completion of a particular output file) that
will be satisfied by the task as it runs, and it can communicate with
other vtasks to find out anyone else's completed postrequisites satisfy
any of its prerequisites.  A vtask can launch its external task when all
its prerequisites are satisfied, after which its internal state
(including the list of completed postrequisites) is updated by the
external task using Python Remote Objects (Pyro). 

See repository documentation for more information.
"""

cycle_time = reference_time( "2008053112" )
    
# Start the pyro nameserver before running this program. There are
# various ways to do this, with various options.  
# See http://pyro.sourceforge.net/manual/5-nameserver.html

daemon = Pyro.core.Daemon()
ns = Pyro.naming.NameServerLocator().getNS()
daemon.useNameServer(ns)

class system_status( Pyro.core.ObjBase ):

    def __init__( self ):
        Pyro.core.ObjBase.__init__(self)
        self.status = "fine and dandy"
    
    def report( self ):
        return self.status

status = system_status() 

uri = daemon.connect( status, "system_status" )

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

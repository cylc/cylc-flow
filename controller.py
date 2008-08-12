#!/usr/bin/python

from vtasks import *
from time import sleep
from reference_time import reference_time 
from ec_globals import dummy_mode

import Pyro.core
import Pyro.naming

"""
========= ECOCONNECT CONTROLLER WITH IMPLICIT SCHEDULING ===============

The controller creates and manages vtask objects that represent external
ecoconnect tasks (defined below). A vtask can launch its external task
when its task-specific prerequisite conditions are satisfied, after which
its internal state is updated to reflect progress of the external task.  

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

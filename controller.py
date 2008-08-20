#!/usr/bin/python

from vtasks_dummy import *
from time import sleep
from reference_time import reference_time 
from spinner import spinner

import Pyro.core
import Pyro.naming
import os

"""
========= ECOCONNECT CONTROLLER WITH IMPLICIT SCHEDULING ===============
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
    tasks.append( A( cycle_time )) 
    tasks.append( B( cycle_time ))
    tasks.append( C( cycle_time ))
    tasks.append( D( cycle_time )) 

    tasks.append( Z( cycle_time )) 

    tasks.append( E( cycle_time ))
    tasks.append( F( cycle_time ))

    for task in tasks:
        uri = daemon.connect( task, task.identity() )

create_tasks()

spnr = spinner()

while True:

    #print " "
    print "handling pyro requests ..."
    daemon.handleRequests(3.0)
    print "... done"
    #status = []
    finished = []

    os.system("clear")
    print ""
    print cycle_time.to_str(), spnr.spin()
    print ""
    for task in tasks:
        task.get_satisfaction( tasks )
        task.run_if_satisfied()
        #status.append( task.get_status() )
        print task.get_status()
        finished.append( task.finished )

    print ""
    #print "checking finished"
    if not False in finished:
        cycle_time.increment()
        print "NEW REFERENCE TIME: " + cycle_time.to_str()
        print ""
        create_tasks()

    #print "sleeping 2" 
    sleep(2)

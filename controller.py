#!/usr/bin/python

from vtasks_dummy import *
from time import sleep
from reference_time import reference_time 

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
        self.status = []

    def reset( self ):
        self.temp_status = []
    
    def report( self ):
        return self.status

    def update( self, str ):
        self.temp_status.append( str )

    def update_finished( self ):
        self.status = self.temp_status


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

# Launch any tasks now that have no prerequisites.  Thereafter, things
# happen only as a result of task state changes via pyro messages.
for task in tasks:
    task.run_if_satisfied()

def process_tasks():

    finished = []
    status.reset()

    status.update( cycle_time.to_str() )
    #print cycle_time.to_str(), spnr.spin()

    for task in tasks:
        task.get_satisfaction( tasks )
        task.run_if_satisfied()
        #print task.get_status()
        status.update( task.get_status() )
        finished.append( task.finished )

    status.update_finished() 

    if not False in finished:
        cycle_time.increment()
        print "NEW REFERENCE TIME: " + cycle_time.to_str()
        create_tasks()


    return 1

# process tasks each time a request is handled
daemon.requestLoop( process_tasks )

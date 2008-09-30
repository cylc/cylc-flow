#!/usr/bin/python

""" 
Program called by the controller to "dummy out" external tasks.

(1) Takes <task name> and <reference time> arguments, which uniquely
    identifies the corresponding task object in the controller.
  
(2) Connects to the said controller task object via Pyro. 

(3) Calls [task object].get_postrequisites() to acquire a list of task
    postrequisites, and sets each of them "satisfied" in turn, with a
    short delay between each.

This allows the entire control program to be tested on the real model
sequence, without actually running the models, so long as model pre- and
post-requisites have been correctly defined, and with the proviso that
the dummy run-times are not currently proportional to the real run times.  
"""

import sys
import Pyro.naming, Pyro.core
from Pyro.errors import NamingError

from time import sleep
import shared

pyro_shortcut = False

# command line arguments
if len( sys.argv ) != 3:
    print "USAGE:", sys.argv[0], "<task name> <REFERENCE_TIME>"
    sys.exit(1)
    
[task_name, ref_time] = sys.argv[1:]

# connect to the task object inside the control program

if pyro_shortcut:
    task = Pyro.core.getProxyForURI("PYRONAME://" + task_name + "_" + ref_time )

else:
    # locate the NS
    locator = Pyro.naming.NameServerLocator()
    print "searching for pyro name server"
    ns = locator.getNS()

    # resolve the Pyro object
    print "resolving " + task_name + '_' + ref_time + " task object"
    try:
        URI = ns.resolve( task_name + '_' + ref_time )
        print 'URI:', URI
    except NamingError,x:
        print "failed: ", x
        raise SystemExit

    # create a proxy for the Pyro object, and return that
    task = Pyro.core.getProxyForURI( URI )

if task_name == "downloader" and shared.run_mode == 1:
    task.incoming( "waiting for incoming files ...")
    # simulate real time mode by delaying downloader
    # input until previous tasks have all finished.

    if pyro_shortcut:
        state = Pyro.core.getProxyForURI("PYRONAME://" + "state" )

    else:
        print "finding system state object"
        try:
            URI = ns.resolve( 'state' )
            print 'URI:', URI
        except NamingError,x:
            print "failed: ", x
            raise SystemExit

        state = Pyro.core.getProxyForURI( URI )

    while True:
        if int( state.get_time_of_oldest_running_task() ) < int( ref_time ):
            sleep(1)
        else:
            break

# set each postrequisite satisfied in turn
for message in task.get_postrequisite_list():
    task.incoming( message )
    #sleep(4)

# finished simulating the external task
task.set_finished()

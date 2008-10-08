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
import reference_time
import datetime

from time import sleep

pyro_shortcut = False

# arguments: <task name> <REFERENCE_TIME> <dummy clock rate>
    
[task_name, ref_time, clock_rate] = sys.argv[1:]

# connect to the task object inside the control program

# need non pyro_shortcut (see below) for clock!
clock = Pyro.core.getProxyForURI("PYRONAME://" + "dummy_clock" )

if pyro_shortcut:
    task = Pyro.core.getProxyForURI("PYRONAME://" + task_name + "_" + ref_time )

else:
    # locate the NS
    locator = Pyro.naming.NameServerLocator()
    #print "searching for pyro name server"
    ns = locator.getNS()

    # resolve the Pyro object
    #print "resolving " + task_name + '%' + ref_time + " task object"
    try:
        URI = ns.resolve( task_name + '%' + ref_time )
    #    print 'URI:', URI
    except NamingError,x:
        print "failed to resolve " + task_name + '%' + ref_time
        print x
        raise SystemExit

    # create a proxy for the Pyro object, and return that
    task = Pyro.core.getProxyForURI( URI )

    est_hrs = task.get_estimated_run_time() / 60.0
    est_dummy_secs = est_hrs * int( clock_rate )

    postreqs = task.get_postrequisite_list()
    n_postreqs = len( postreqs )
    delay = est_dummy_secs / ( n_postreqs - 1 )

if task_name == "downloader":

    rt = reference_time._rt_to_dt( ref_time )
    rt_3p25 = rt + datetime.timedelta( 0,0,0,0,0,3.25,0 )  # 3hr:15min after the hour
    dt = clock.get_datetime()
    if dt >= rt_3p25:
        task.incoming( 'NORMAL', 'CATCHUP: input files already exist for ' + ref_time )
    else:
        task.incoming( 'NORMAL', 'UPTODATE: waiting for input files for ' + ref_time )
        while True:
            dt = clock.get_datetime()
            if dt >= rt_3p25:
                break
            sleep(2)

elif task_name == "topnet":

    rt = reference_time._rt_to_dt( ref_time )
    rt_p25 = rt + datetime.timedelta( 0,0,0,0,0,0.25,0 ) # 15 min past the hour
    dt = clock.get_datetime()
    if not dt >= rt_p25:
        task.incoming( 'NORMAL', 'CATCHUP: passed streamflow data time already, for ' + ref_time )
    else:
        task.incoming( 'NORMAL', 'UPTODATE: waiting for streamflow data time, for ' + ref_time )
        #task.incoming( 'NORMAL', 'UPTODATE for ' + ref_time )
        while True:
            dt = clock.get_datetime()
            if dt >= rt_p25:
                break
            sleep(2)

# set each postrequisite satisfied in turn
task.incoming( "NORMAL", postreqs[0] )
for message in postreqs[1:]:
    sleep(delay)
    task.incoming( "NORMAL", message )

# finished simulating the external task
task.set_finished()

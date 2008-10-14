#!/usr/bin/python

""" 
Program called by the controller to "dummy out" external tasks.

(1) Takes <task name> and <reference time> arguments, which uniquely
    identifies the corresponding task object in the controller.
  
(2) Connects to the relevant controller task object via Pyro. 

(3) gets a list of timed task postrequisites for the object, and sets
    each of them "satisfied" in turn, at the right time.

This allows the control system to be tested without running the real
tasks, so long as model pre- and post-requisites have been correctly
defined and postrequisite completion time estimates are accurate (and
with the proviso that the real tasks may be delayed by resource
contention in addition to sequencing constraints).
"""

import sys
import Pyro.naming, Pyro.core
from Pyro.errors import NamingError
import reference_time
import datetime

from time import sleep

# unpack script arguments: <task name> <REFERENCE_TIME> <clock rate>
[task_name, ref_time, clock_rate] = sys.argv[1:]

# getProxyForURI is the shortcut way to a pyro object proxy; it may
# be that the long way is better for error checking; see pyro docs.
task = Pyro.core.getProxyForURI("PYRONAME://" + task_name + "%" + ref_time )

# Connect just once for the clock.  Real models will use the OS clock,
# so no connection will be made, but here we need to consult the main
# program's accelerated dummy mode clock.
clock = Pyro.core.getProxyForURI("PYRONAME://" + "dummy_clock" )

if task_name == "downloader":

    rt = reference_time._rt_to_dt( ref_time )
    rt_3p25 = rt + datetime.timedelta( 0,0,0,0,0,3.25,0 )  # 3hr:15min after the hour
    if clock.get_datetime() >= rt_3p25:
        task.incoming( 'NORMAL', 'CATCHUP: input files already exist for ' + ref_time )
    else:
        task.incoming( 'NORMAL', 'UPTODATE: waiting for input files for ' + ref_time )
        while True:
            sleep(1)
            if clock.get_datetime() >= rt_3p25:
                break

elif task_name == "topnet":

    rt = reference_time._rt_to_dt( ref_time )
    rt_p25 = rt + datetime.timedelta( 0,0,0,0,0,0.25,0 ) # 15 min past the hour
    # THE FOLLOWING MESSAGES MUST MATCH THOSE IN topnet.incoming()
    if clock.get_datetime() >= rt_p25:
        task.incoming( 'NORMAL', 'CATCHUP: streamflow data available, for ' + ref_time )
    else:
        task.incoming( 'NORMAL', 'UPTODATE: waiting for streamflow, for ' + ref_time ) 
        while True:
            sleep(1)
            if clock.get_datetime() >= rt_p25:
                break

# set each postrequisite satisfied in turn
start_time = clock.get_datetime()

postreq_dict = task.get_postrequisites()
completion_times = task.get_postrequisite_times()
postreqs = postreq_dict.keys()
done = {}
time = {}

for req in postreqs:
    done[ req ] = False
    hours = completion_times[ req] / 60.0
    time[ req ] = start_time + datetime.timedelta( 0,0,0,0,0,hours,0)

while True:
    sleep(1)
    dt = clock.get_datetime()
    all_done = True
    for req in postreqs:
        if not done[ req]:
            if dt >= time[ req ]:
                #print "SENDING MESSAGE: ", time[ req ], req
                task.incoming( "NORMAL", req )
                done[ req ] = True
            else:
                all_done = False

    if all_done:
        break

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
import Pyro.core

from time import sleep

# command line arguments
if len( sys.argv ) != 3:
    print "USAGE:", sys.argv[0], "<task name> <REFERENCE_TIME>"
    sys.exit(1)
    
[task_name, ref_time] = sys.argv[1:]

# connect to the task object inside the control program
task = Pyro.core.getProxyForURI("PYRONAME://" + task_name + "_" + ref_time )

# set each postrequisite satisfied in turn
for message in task.get_postrequisite_list():
    sleep(5)
    task.set_satisfied( message )

# finished simulating the external task
task.set_finished()

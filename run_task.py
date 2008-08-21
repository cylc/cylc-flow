#!/usr/bin/python

# EXTERNAL TASK DUMMY PROGRAM 

# connects to the proper controller task object via pyro, 
# gets its list of postrequisites, and sets each of them 
# each in turn

import sys
import Pyro.core

from time import sleep
from reference_time import reference_time

if len( sys.argv ) != 3:
    print "USAGE:", sys.argv[0], "<task name> <REFERENCE_TIME>"
    sys.exit(1)
    
[task_name, ref_time] = sys.argv[1:]
reference_time = reference_time( ref_time )

# connect to the task object inside the control program
task = Pyro.core.getProxyForURI("PYRONAME://" + task_name + "_" + reference_time.to_str() )


for message in task.get_postrequisites():
    sleep(5)
    task.set_satisfied( message )

sleep(5)
task.set_finished()

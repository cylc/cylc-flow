#!/usr/bin/python

""" 
Standalone interface between external EcoConnect tasks/models and the
task objects that represent them in the controller.

(1) Takes <task name> and <reference time> arguments 
    (which uniquely identifies the task object in the controller),
    and a <message> string to send directly to the task object.
  
(2) Connects to the controller task object via Pyro. 

(3) Calls [task object].incoming(<message>) to send the message.
"""

import sys
import Pyro.core
from pyro_ns_name import pyro_object_name

# command line arguments
if len( sys.argv ) != 5:
    print "USAGE:", sys.argv[0], "<priority> <task name> <REFERENCE_TIME> <quoted message>"
    print "   priority: CRITICAL, WARNING, or NORMAL"
    sys.exit(1)
    
[priority, task_name, ref_time] = sys.argv[1:4]
message = sys.argv[4]

# TO DO: use exception handling when I know how to report the real error
# (which is generally more useful than my own error message)

# connect to the task object inside the control program
try:
    task = Pyro.core.getProxyForURI('PYRONAME://' + pyro_object_name( task_name + '%' + ref_time ) )
    task.incoming( priority, message )
except:
    # nameserver not found, or object not registered with it?
    print "ERROR: failed to connect to " + task_name + "_" + ref_time
    print "Trying dead letter box"

    try:
        dead_box = Pyro.core.getProxyForURI('PYRONAME://' + pyro_object_name( 'dead_letter_box' ))
        dead_box.incoming( message )
    except:
        # nameserver not found, or object not registered with it?
        print "ERROR: failed to connect to pyro nameserver"
        sys.exit(1)


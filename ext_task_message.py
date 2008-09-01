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

# command line arguments
if len( sys.argv ) != 4:
    print "USAGE:", sys.argv[0], "<task name> <REFERENCE_TIME> <message>"
    sys.exit(1)
    
[task_name, ref_time] = sys.argv[1:3]
message = sys.argv[3]

# TO DO: use exception handling when I know how to report the real error
# (which is generally more useful than my own error message!)

# connect to the task object inside the control program
#try:
task = Pyro.core.getProxyForURI("PYRONAME://" + task_name + "_" + ref_time )
#except:
# nameserver not found, or object not registered with it?
#    print "ERROR: failed to connect to pyro nameserver"

#try:
task.incoming( message )
#except:
#    print "ERROR: failed to send message"

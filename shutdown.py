#!/usr/bin/python

""" 
Tell the task manager (via Pyro) to shut down. 
"""

import sys
import Pyro.core

# command line arguments
if len( sys.argv ) != 1:
    print "USAGE:", sys.argv[0]
    sys.exit(1)
    
# connect to the task object inside the control program
try:
    god = Pyro.core.getProxyForURI("PYRONAME://god")
    god.clean_shutdown()
except:
    # nameserver not found, or god not registered with it?
    print "ERROR: failed to talk to god"
    print "Trying dead letter box"

    try:
        dead_box = Pyro.core.getProxyForURI("PYRONAME://" + "dead_letter_box" )
        dead_box.incoming( message )
    except:
        # nameserver not found, or object not registered with it?
        print "ERROR: failed to connect to pyro nameserver"
        sys.exit(1)

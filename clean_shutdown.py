#!/usr/bin/python

""" 
Tell the task manager (via Pyro) to shut down. 
"""

import os
import sys
import Pyro.core
from time import sleep
import config     # for dummy_mode

# command line arguments
if len( sys.argv ) != 1:
    print "USAGE:", sys.argv[0]
    sys.exit(1)

   
try:
    # connect to the task object inside the control program
    god = Pyro.core.getProxyForURI("PYRONAME://god")
    # pause to prevent new dummy tasks being launched after the pkill 
    god.request_pause()
    print 'pausing system ...'
    sleep(5)

    if config.dummy_mode:
        print 'killing dummy tasks ...'
        # kill any running task_dummy programs
        os.system( 'pkill -9 -u $USER task_dummy.py' )
        sleep(5)

    # shutdown the controller and pyro nameserver
    print 'requesting shutdown ...'
    god.request_shutdown()

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

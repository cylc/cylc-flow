#!/usr/bin/python

""" 
Tell the task manager (via Pyro) to shut down. 
"""

import os
import sys
import Pyro.core
from time import sleep
import config     # for dummy_mode

def usage():
    print 'USAGE: ' + sys.argv[0] + '[-p] [-r] [-s]'
    print 'options:'
    print '  -p    pause task processing'
    print '  -r    resume task processing'
    print '  -s    shutdown the controller'
 
# command line arguments
if len( sys.argv ) != 2:
    usage()
    sys.exit(1)

pause = False
resume = False
shutdown = False

if sys.argv[1] == '-p':
    pause = True
elif sys.argv[1] == '-r':
    resume = True
elif sys.argv[1] == '-s':
    shutdown = True
else:
    usage()
    sys.exit(1)
   

try:
    # connect to the task object inside the control program
    god = Pyro.core.getProxyForURI("PYRONAME://god")

except:
    print "ERROR: failed to connect to god"
    sys.exit(1)

try:
    if pause:
        god.request_pause()

    elif resume:
        god.request_resume()

    elif shutdown:

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

    else:
        print "ERROR: should not be here"
        sys.exit(1)

except:
    # nameserver not found, or god not registered with it?
    print "ERROR: failed to talk to god; trying dead letter box"

    try:
        dead_box = Pyro.core.getProxyForURI("PYRONAME://" + "dead_letter_box" )
        try:
            dead_box.incoming( message )
        except:
            print "ERROR: failed to send dead letter"
            sys.exit(1)   
    except:
        # nameserver not found, or object not registered with it?
        print "ERROR: failed to connect to pyro nameserver"
        sys.exit(1)

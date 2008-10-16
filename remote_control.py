#!/usr/bin/python

""" 
Tell the task manager (via Pyro) to shut down. 
"""

import os
import sys
import Pyro.core
from time import sleep
from pyro_ns_naming import pyro_ns_name

def usage():
    print 'USAGE: ' + sys.argv[0] + ' [-p] [-r] [-s] [-b <hours>]'
    print 'options:'
    print '  -p    pause task processing'
    print '  -r    resume task processing'
    print '  -s    shutdown the controller'
    print '  -b <hours> bump dummy time clock forward by <hours>'
 
# command line arguments
n_args = len( sys.argv ) -1

pause = False
resume = False
shutdown = False
bump_hours = 0

dummy_mode = False

if n_args == 1: 
    if sys.argv[1] == '-p':
        pause = True
    elif sys.argv[1] == '-r':
        resume = True
    elif sys.argv[1] == '-s':
        shutdown = True
    else:
        usage()
        sys.exit(1)


elif n_args == 2 and sys.argv[1] == '-b':
    # bump dummy clock
    bump_hours = sys.argv[2]

    try:
        dummy_clock = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_name( 'dummy_clock'))
    except:
        print "ERROR: failed to connect to god"
        sys.exit(1)

    try:
        print "current time: " + str( dummy_clock.get_datetime() )
        print "bumped on to: " + str( dummy_clock.bump( bump_hours ))
    except:
        print "ERROR: failed to bump dummy clock"
        sys.exit(1)   
 
    sys.exit(0)



else:
    usage()
    sys.exit(1)

   

# pause, resume, or halt
try:
    # connect to the task object inside the control program
    god = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_name( 'god'))

    if god.in_dummy_mode():
        dummy_mode = True
 
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
        
        if dummy_mode:
            print 'killing any dummy tasks ...'
            # kill any running 'dummy_task's
            os.system( 'pkill -9 -u $USER dummy_task.py' )
            sleep(5)

        # shutdown the controller and pyro nameserver
        print 'requesting shutdown ...'
        god.request_shutdown()

        print "FIX ME: you now need to send a message to an existing task"
        print "to cause the processing loop to activate again and effect"
        print "the final shutdown."

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

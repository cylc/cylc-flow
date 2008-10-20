#!/usr/bin/python

import os
import sys
import Pyro.core
from time import sleep
from pyro_ns_naming import pyro_ns_name
import config

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
        print "ERROR: failed to connect to the dummy clock"
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
    control = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_name( 'master'))

except:
    print "ERROR: failed to connect to control"
    raise
    #sys.exit(1)

try:
    if pause:
        control.pause()

    elif resume:
        control.resume()

    elif shutdown:

        # pause to prevent new dummy tasks being launched after the pkill 
        control.pause()
        print 'pausing system ...'
        sleep(5)
        
        if config.dummy_mode:
            print 'killing any dummy tasks ...'
            # kill any running 'dummy_task's
            os.system( 'pkill -9 -u $USER dummy_task.py' )
            sleep(5)

        # shutdown the controller and pyro nameserver
        print 'requesting shutdown ...'
        control.shutdown()

        #the following may still be necessary:
        #print "you may now need to send a message to an existing task"
        #print "to reactivate task processing and effect the shutdown."

    else:
        print "ERROR: should not be here"
        sys.exit(1)

except:
    # nameserver not found, or control not registered with it?
    print "ERROR: failed to talk to control; trying dead letter box"
    raise

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

#!/usr/bin/python

import os
import sys
import pyrex
import Pyro.core
from optparse import OptionParser
from time import sleep

# construct a command line parser
parser = OptionParser( "usage: %prog [options] system-name" )

parser.add_option( "-p", "--pause", help="pause system",
        action="store_true", default=False, dest="pause" )

parser.add_option( "-r", "--resume", help="resume system",
        action="store_true", default=False, dest="resume" )

parser.add_option( "-s", "--shutdown", help="shutdown system",
        action="store_true", default=False, dest="shutdown" )

verbosity_choices = ['debug','info', 'warning', 'error', 'critical'] 

parser.add_option( "-v", "--verbosity",
        help="set verbosity: " + ', '.join(verbosity_choices),
        action="store", 
        choices=verbosity_choices,
        dest="verbosity" )

parser.add_option( "-b", "--bump", help="bump dummy clock forward (hours)",
        type="int", action="store", dest="bump_hours" )

if len( sys.argv ) == 1:
    # no options or args supplied
    parser.print_help()
    sys.exit(1)

# get command line options and positional args
( options, args ) = parser.parse_args()

if len( args ) != 1:
    parser.error( "incorrect number of arguments" )

ns_groups = pyrex.discover()

system_name = args[0]

if ns_groups.registered( system_name ):
    print "system: " + system_name
else:
    print "WARNING: no " + system_name + " registered in the Pyro nameserver"
    ns_groups.print_info()
    sys.exit(1)


try:
    # connect to the remote switch object in sequenz
    control = Pyro.core.getProxyForURI('PYRONAME://' + system_name + '.' + 'remote_control' )
except:
    print "ERROR: failed to connect to control"
    raise

if options.pause:
    control.pause()

if options.resume:
    control.resume()

if options.shutdown:
    if control.get_config( 'dummy_mode' ):
        # pause to prevent new dummy tasks being launched after the pkill 
        control.pause()
        print 'pausing system ...'
        sleep(5)
        print 'killing any dummy tasks ...'
        # kill any running 'dummy_task's
        os.system( 'pkill -9 -u $USER dummy-task.py' )
        sleep(5)

    control.shutdown()

if options.verbosity:
    print "requesting verbosity " + options.verbosity
    control.set_verbosity( options.verbosity )

if options.bump_hours:
    try:
        dummy_clock = Pyro.core.getProxyForURI('PYRONAME://' + system_name + '.' + 'dummy_clock' )
    except:
        print "ERROR: failed to connect to the dummy clock"
        sys.exit(1)
    print "current time: " + str( dummy_clock.get_datetime() )
    print "bumped on to: " + str( dummy_clock.bump( options.bump_hours ))

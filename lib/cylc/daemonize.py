#!/usr/bin/env python

import os, sys
from suite_output import suite_output

def daemonize( suite, port ):
    """
    ATTRIBUTION: base on a public domain code recipe by Jurgen Hermann:
    http://code.activestate.com/recipes/66012-fork-a-daemon-process-on-unix/
    """

    # Do the UNIX double-fork magic, see Stevens' "Advanced
    # Programming in the UNIX Environment" for details (ISBN 0201563177)

    sout = suite_output( suite )

    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError, e:
        print >>sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent, print eventual PID before
            print "\nSuite Info:"
            print " + Name:", suite
            print " + PID: ", pid
            print " + Port:", port
            print " + Logs: %s/(log|out|err)" % os.path.dirname( sout.get_path() )
            print
            print "To see if this suite is still running:"
            print " * cylc scan"
            print " * cylc ping -v", suite
            print " * ps -fu $USER | grep 'cylc-run .*", suite + "'"
            print
            print "To run in non-daemon mode use --debug."
            print "For more information type 'cylc --help'."
            print
            sys.exit(0)
    except OSError, e:
        print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    # reset umask
    os.umask(022) # octal

    # redirect output to the suite log files
    sout.redirect()

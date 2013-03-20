#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
from time import sleep, time

class poller( object ):
    """Encapsulates polling activity for cylc commands. Derived classes
    must override the check() method to test the polling condition. Call
    check_once() instead of poll() for a one-off check on the condition."""

    @classmethod
    def add_to_cmd_options( cls, parser ):
        """Add common command line options for polling."""

        # Only long option names to reduce chance of conflicts,
        # but if necessary could take variable and option name args.

        parser.add_option( "--wait",
            help="Wait for the suite to stop before exiting",
            action="store_true", dest="wait", default=False )

        parser.add_option( "--timeout",
            help="(with -w/--wait) Maximum time in seconds to "
            "wait for the result before exiting with error "
            "status (default: no timeout).",
            action="store", dest="timeout", default=None )

        parser.add_option( "--interval",
            help="(with -w/--wait) Polling interval in seconds (default=5).",
            action="store", dest="interval", default=5 )

    def __init__( self, condition, timeout=None, interval=5, args={} ):

        self.condition = condition # e.g. "suite stopped"

        if timeout:
            """check timeout is a number"""
            try:
                timeout = float(timeout)
            except:
                sys.stderr.write("timeout must be a number\n")
                sys.exit(1)

        """check interval is a number"""
        try:
            interval = float(interval)
        except:
            sys.stderr.write("interval must be a number\n")
            sys.exit(1)

        self.timeout = timeout
        self.interval = interval
        self.args = args # any extra parameters needed by check()
        self.starttime = None

    def _timed_out( self ):
        """Return True if we've timed out"""
        if not self.timeout:
            # never timeout
            return False
        else:
            # check if we've timed out
            if not self.starttime:
                # set the start time
                self.starttime = time()
            return ( (time() - self.starttime) > self.timeout )

    def check_once( self ): 
        """Provide self.check() in derived classes to test the polling
        condition - return True if condition met, else False."""

        print "checking for condition '" + self.condition + "'"
        if self.check():
            print "condition '" + self.condition + "' satisfied"
            return True
        else:
            print >> sys.stderr, "ERROR: condition '" + self.condition + "' not satisfied"
            return False

    def poll( self ):
        """Poll for the condition embodied by self.check(). Return True
        if condition met, or False on time out."""

        print "polling for condition '" + self.condition + "'", 
        done = False 
        while not ( done or self._timed_out() ):
            if self.check():
                done = True 
            else:
                sys.stdout.write('.')
                sleep( self.interval )
        sys.stderr.write('\n')

        if done:
            print "condition '" + self.condition + "' achieved"
            return True
        else:
            print >> sys.stderr, "ERROR: timed out before condition '" + self.condition + "' achieved"
            return False


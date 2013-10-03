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
    must override the check() method to test the polling condition."""

    @classmethod
    def add_to_cmd_options( cls, parser, d_interval=60, d_max_polls=10 ):
        # add command line options for polling
        parser.add_option( "--max-polls",
            help="Maximum number of polls (default " + str(d_max_polls) + ").",
            metavar="INT", action="store", dest="max_polls", default=d_max_polls )
        parser.add_option( "--interval",
            help="Polling interval in seconds (default " + str(d_interval) + ").",
            metavar="SECS", action="store", dest="interval", default=d_interval )

    def __init__( self, condition, interval, max_polls, args={} ):

        self.condition = condition # e.g. "suite stopped"

        """check max_polls is an int"""
        try:
            self.max_polls = int(max_polls)
        except:
            sys.stderr.write("max_polls must be an int\n")
            sys.exit(1)

        """check interval is an int"""
        try:
            self.interval = int(interval)
        except:
            sys.stderr.write("interval must be an integer\n")
            sys.exit(1)

        self.n_polls = 0
        self.args = args # any extra parameters needed by check()

    def poll( self ):
        """Poll for the condition embodied by self.check().
        Return True if condition met, or False if polling exhausted."""

        if self.max_polls == 0:
            print >> sys.stderr, "WARNING, --max-polls=0: nothing to do"
            sys.exit(0)
        elif self.max_polls == 1:
            sys.stdout.write( "checking " )
        else:
            sys.stdout.write( "polling " )
        sys.stdout.write( "for '" + self.condition + "'" )

        done = False 
        while ( not done and self.n_polls < self.max_polls ):
            self.n_polls += 1
            if self.check():
                done = True 
            else:
                if self.max_polls > 1:
                    sys.stdout.write('.')
                    sleep( self.interval )
        if done:
            sys.stdout.write( ": satisfied\n" )
            return True
        else:
            print
            print >> sys.stderr, " ERROR: condition not satisfied",
            if self.max_polls > 1:
                print >> sys.stderr, "after " + str(self.max_polls) + " polls"
            else:
                print >> sys.stderr, ""
            return False


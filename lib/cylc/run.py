#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

"""Provide the main function for "cylc run" and "cylc restart"."""

import sys

global debug
debug = True

def main(name, start):

    # local invocation
    try:
        server = start()
    except Exception, x:
        if debug:
            raise
        else:
            print >> sys.stderr, x
            print >> sys.stderr, "(use --debug to see exception traceback)"
            sys.exit(1)
    try:
        server.run()
        #   For profiling:
        #import cProfile
        #cProfile.run( 'server.run()', 'fooprof' )
        #   and see Python docs "The Python Profilers"
        #   for how to display the resulting stats.
    except Exception, x:
        print >> sys.stderr, "ERROR CAUGHT, will clean up before exit"
        # this assumes no exceptions in shutdown():
        server.shutdown( 'ERROR: ' + str(x) )

        if debug:
            raise
        else:
            print >> sys.stderr, "THE ERROR WAS:"
            print >> sys.stderr, x
            print >> sys.stderr, "(use --debug to see exception traceback)"
            sys.exit(1)
    except:
        # (note: to catch SystemExit use "except BaseException")
        print >> sys.stderr, "ERROR CAUGHT; will clean up before exit"
        server.shutdown('!cylc error - please report!')
        raise
    else:
        server.shutdown('Suite shutting down')

def set_main_debug(mode):
    global debug
    debug = mode

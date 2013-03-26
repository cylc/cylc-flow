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

"""Provide the main function for "cylc run" and "cylc restart"."""

import sys
from daemonize import daemonize
from version import cylc_version

def print_blurb():
    lines = []
    lines.append( " The Cylc Suite Engine [" + cylc_version + "] " )
    lines.append( " Copyright (C) 2008-2013 Hilary Oliver, NIWA " )

    lic = """
 This program comes with ABSOLUTELY NO WARRANTY.  It is free software; 
 you are welcome to redistribute it under certain conditions. Details: 
  `cylc license conditions'; `cylc license warranty' """
    lines += lic.split('\n')

    mx = 0
    for line in lines:
        if len(line) > mx:
            mx = len(line)

    print '*' * (mx + 2)
    for line in lines:
        print '*' + line.center( mx ) + '*'
    print '*' * (mx + 2)

def main(name, start):

    # Parse the command line:
    server = start()

    # Print copyright and license information
    print_blurb()

    # Configure Pyro to get the port file, to check the suite is not
    # already running, before daemonizing.
    try:
        server.configure_pyro()
    except Exception, x:
        if server.options.debug:
            raise
        else:
            print >> sys.stderr, x
            sys.exit(1)
 
    # Daemonize the suite
    if not server.options.debug:
        daemonize( server.suite, server.port )

    try:
        server.configure()
        server.run()
        #   For profiling:
        #import cProfile
        #cProfile.run( 'server.run()', 'fooprof' )
        #   and see Python docs "The Python Profilers"
        #   for how to display the resulting stats.
    except Exception, x:
        print >> sys.stderr, "ERROR CAUGHT: cleaning up before exit"
        raise
        try:
            server.shutdown( 'ERROR: ' + str(x) )
        except Exception, y:
            # In case of exceptions in the shutdown method itself
            print str(y)
            pass
        if server.options.debug:
            raise
        else:
            print >> sys.stderr, "THE ERROR WAS:"
            print >> sys.stderr, x
            print >> sys.stderr, "use --debug to turn on exception tracebacks)"
            sys.exit(1)
    else:
        server.shutdown()


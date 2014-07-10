#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
from cfgspec.site import sitecfg
import flags
from exceptions import SchedulerStop, SchedulerError

def print_blurb():
    lines = []
    lines.append( " The Cylc Suite Engine [" + cylc_version + "] " )
    lines.append( " Copyright (C) 2008-2014 Hilary Oliver, NIWA " )

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

    # Before daemonizing attempt to create the suite output tree and get
    # the suite port file.

    try:
        if server.__class__.__name__ != 'restart':
            sitecfg.create_cylc_run_tree( server.suite )
        server.configure_pyro()
    except Exception, x:
        if flags.debug:
            raise
        else:
            print >> sys.stderr, x
            sys.exit(1)

    # Daemonize the suite
    if not server.options.no_detach and not flags.debug:
        daemonize( server.suite, server.port )

    try:
        server.configure()
        server.run()
        #   For profiling:
        #import cProfile
        #cProfile.run( 'server.run()', 'fooprof' )
        #   and see Python docs "The Python Profilers"
        #   for how to display the resulting stats.
    except SchedulerStop, x:
        # deliberate stop
        print str(x)
        server.shutdown()

    except SchedulerError, x:
        print >> sys.stderr, str(x)
        server.shutdown()
        sys.exit(1)

    except KeyboardInterrupt as x:
        import traceback
        try:
            server.shutdown(str(x))
        except Exception as y:
            # In case of exceptions in the shutdown method itself.
            traceback.print_exc(y)
            sys.exit(1)

    except (KeyboardInterrupt,Exception) as x:
        import traceback
        traceback.print_exc(x)
        print >> sys.stderr, "ERROR CAUGHT: cleaning up before exit"
        try:
            server.shutdown( 'ERROR: ' + str(x) )
        except Exception, y:
            # In case of exceptions in the shutdown method itself
            traceback.print_exc(y)
        if flags.debug:
            raise
        else:
            print >> sys.stderr, "THE ERROR WAS:"
            print >> sys.stderr, x
            print >> sys.stderr, "use --debug to turn on exception tracebacks)"
            sys.exit(1)
    else:
        # main loop ends (not used?)
        server.shutdown()


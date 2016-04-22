#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Provide the main function for "cylc run" and "cylc restart"."""

import sys
import traceback
from cylc.daemonize import daemonize
from cylc.mp_pool import SuiteProcPool
from cylc.version import CYLC_VERSION
from cylc.cfgspec.globalcfg import GLOBAL_CFG, GlobalConfigError
import cylc.flags
from cylc.exceptions import SchedulerStop, SchedulerError
from parsec.validate import IllegalItemError


def print_blurb():
    logo = (
        "            ,_,       \n"
        "            | |       \n"
        ",_____,_, ,_| |_____, \n"
        "| ,___| | | | | ,___| \n"
        "| |___| |_| | | |___, \n"
        "\_____\___, |_\_____| \n"
        "      ,___| |         \n"
        "      \_____|         \n"
    )
    license = """
The Cylc Suite Engine [%s]
Copyright (C) 2008-2016 NIWA
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
This program comes with ABSOLUTELY NO WARRANTY;
see `cylc warranty`.  It is free software, you
are welcome to redistribute it under certain
conditions; see `cylc conditions`.

  """ % CYLC_VERSION

    logo_lines = logo.splitlines()
    license_lines = license.splitlines()
    lmax = max(len(line) for line in license_lines)
    for i in range(len(logo_lines)):
        print logo_lines[i], ('{0: ^%s}' % lmax).format(license_lines[i])
    print


def main(name, start):
    # Parse the command line:
    server = start()
    GLOBAL_CFG.create_cylc_run_tree(server.suite)

    try:
        # Load suite.rc, before starting and daemonizing server, so errors are
        # reported to screen
        server.load_suiterc()
    except (GlobalConfigError, IllegalItemError) as exc:
        if cylc.flags.debug:
            raise
        else:
            sys.exit('ERROR: configuration: ' + str(exc))

    # Create run directory tree and get port.
    try:
        server.configure_pyro()
    except Exception as exc:
        try:
            server.shutdown('ERROR: ' + str(exc))
        finally:
            raise

    # Print copyright and license information
    print_blurb()

    # Daemonize the suite
    if not server.options.no_detach and not cylc.flags.debug:
        daemonize(server)

    try:
        # Start the worker pools
        SuiteProcPool.get_inst()

        server.configure()
        server.run()
        # For profiling (see Python docs for how to display the stats).
        # import cProfile
        # cProfile.runctx('server.run()', globals(), locals(), 'stats')
    except SchedulerStop as x:
        # deliberate stop
        print str(x)
        server.shutdown()

    except SchedulerError as x:
        server.shutdown('ERROR: ' + str(x))
        if cylc.flags.debug:
            raise
        sys.exit(str(x))

    except (KeyboardInterrupt, Exception) as x:
        traceback.print_exc(x)
        print >> sys.stderr, "ERROR CAUGHT: cleaning up before exit"
        try:
            server.shutdown('ERROR: ' + str(x))
        except Exception as y:
            # In case of exceptions in the shutdown method itself
            traceback.print_exc(y)
        raise

    else:
        # main loop ends (not used?)
        server.shutdown()

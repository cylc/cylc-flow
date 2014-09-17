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

"""Determine the cylc version string; repository or raw source distribution."""

import os, sys
import run_get_stdout

cylc_dir = os.environ['CYLC_DIR']
vfile = os.path.join( cylc_dir, 'VERSION' )
gitd = os.path.join( cylc_dir, '.git' )

if os.path.isdir( gitd ) or os.path.isfile( gitd ):
    # We're running in a cylc git repository, so dynamically determine
    # the cylc version string.
    script = os.path.join( cylc_dir, 'admin', 'get-repo-version' )
    res = run_get_stdout.run_get_stdout( script )
    if res[0]:
        cylc_version = res[1][0]
        os.environ["CYLC_VERSION"] = cylc_version
    else:
        raise SystemExit( "Failed to get version number!")

else:
    # We're running in a raw cylc source tree, so read the version
    # file created by 'make' after unpacking the tarball.
    try:
        cylc_version = open(vfile).readline().rstrip()
        os.environ["CYLC_VERSION"] = cylc_version
    except IOError, x:
        print >> sys.stderr, x
        print >> sys.stderr, "\n*** ERROR, failed to read the cylc VERSION file.***\n"
        print >> sys.stderr, """Please inform your cylc admin user. This file should have been created
by running 'make' or 'make version' after unpacking the cylc release tarball."""
        sys.exit("ABORTING")

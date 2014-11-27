#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
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

import os
from cylc.run_get_stdout import run_get_stdout


def _get_cylc_version():
    """Determine and return cylc version string."""

    cylc_dir = os.environ['CYLC_DIR']

    if os.path.exists(os.path.join(cylc_dir, ".git")):
        # We're running in a cylc git repository, so dynamically determine
        # the cylc version string.
        res = run_get_stdout(
            os.path.join(cylc_dir, "admin", "get-repo-version"))
        if res[0]:
            return res[1][0]
        else:
            raise SystemExit("Failed to get version number!")

    else:
        # We're running in a raw cylc source tree, so read the version
        # file created by 'make' after unpacking the tarball.
        try:
            for line in open(os.path.join(cylc_dir, 'VERSION')):
                return line.rstrip()
        except IOError:
            raise SystemExit(
                "*** ERROR, failed to read the cylc VERSION file.***\n" +
                "Please inform your cylc admin user.\n" +
                "This file should have been created by running 'make' or\n" +
                "'make version' after unpacking the cylc release tarball.\n" +
                "ABORTING")


CYLC_VERSION = _get_cylc_version()
os.environ["CYLC_VERSION"] = CYLC_VERSION

#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

"""Determine the cylc version string; repository or raw source distribution."""

import os
from cylc.run_get_stdout import run_get_stdout


UNKNOWN = "UNKNOWN"


def _get_cylc_version():
    """Determine and return cylc version string."""

    cylc_dir = os.environ['CYLC_DIR']

    if os.path.exists(os.path.join(cylc_dir, ".git")):
        # We're running in a cylc git repository, so dynamically determine
        # the cylc version string.  Enclose the path in quotes to handle
        # avoid failure when cylc_dir contains spaces.
        is_ok, outlines = run_get_stdout('"%s"' % os.path.join(
            cylc_dir, "etc", "dev-bin", "get-repo-version"))
        if is_ok and outlines:
            return outlines[0]
        else:
            return UNKNOWN

    else:
        # We're running in a raw cylc source tree, so read the version
        # file created by 'make' after unpacking the tarball.
        try:
            for line in open(os.path.join(cylc_dir, 'VERSION')):
                return line.rstrip()
        except IOError:
            return UNKNOWN


CYLC_VERSION = _get_cylc_version()
os.environ["CYLC_VERSION"] = CYLC_VERSION

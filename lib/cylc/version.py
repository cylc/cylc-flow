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

import os, sys
import subprocess

# auto-replaced with version tag by new-release script:
cylc_version = "VERSION-TEMPLATE"
cylc_dir = os.environ['CYLC_DIR']

if cylc_version == "VERSION-" + "TEMPLATE": # (to avoid the replacement)
    # This must be a cylc repository, or a copy of the repository
    # source: use git to get a qualified most recent version tag.
    cwd = os.getcwd()
    os.chdir( cylc_dir )
    try:
        p = subprocess.Popen( ['git', 'describe' ], stdout=subprocess.PIPE, stderr=subprocess.PIPE )
    except OSError,x:
        # git not found, 
        cylc_version = "(DEV)"
    else:
        retcode = p.wait()
        if retcode != 0:
            # 'git describe' failed - this must be a copy of the
            # repository source but not a proper clone or a release.
            cylc_version = "(DEV)"
        else:
            # got a pseudo version number
            out, err = p.communicate()
            cylc_version = out.rstrip()
    os.chdir(cwd)


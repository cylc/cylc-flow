#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
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

import os, sys
import atexit
import shutil
from tempfile import mkdtemp
from cylc.mkdir_p import mkdir_p

"""
MODULE FOR GLOBAL CONFIGURATION DATA

Much of the information here should ultimately end up in a sensible 
site and host configuration file or similar.
"""

# PYRO CONFIGURATION ###################################################
  # base port (the lowest allowed socket number)
pyro_base_port = 7766   # (7766 is the Pyro default)
  # max number of ports starting from base port
pyro_port_range = 100 # (100 is the Pyro default)

# SUITE REGISTRATION DATABASE LOCATION #################################
  # Local registrations, user-specific
local_regdb_path = os.path.join( os.environ['HOME'], '.cylc', 'DB' )

# CYLC TEMPORARY DIRECTORY #############################################
try:
    cylc_tmpdir = os.environ['CYLC_TMPDIR']
except KeyError:
    # use tempfile.mkdtemp() to create a new temp directory
    cylc_tmpdir = mkdtemp(prefix="cylc-")
    atexit.register(lambda: shutil.rmtree(cylc_tmpdir))
else:
    # if CYLC_TMPDIR was set, create the dir if necessary
    try:
        mkdir_p( cylc_tmpdir )
    except Exception,x:
        print >> sys.stderr, x
        print >> sys.stderr, 'ERROR, conf/CylcGlobals.py: illegal temp dir?', cylc_tmpdir
        sys.exit(1)
#print "Cylc Temp Dir is:", cylc_tmpdir


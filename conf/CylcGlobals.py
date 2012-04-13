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

"""
MODULE FOR GLOBAL CONFIGURATION DATA

ssh-base task messaging may be required from some remote task hosts but
not others, in which case the content of this file may vary by host
machine.

Much of the information here should ultimately end up in a sensible 
site and host configuration file or similar.
"""

# PYRO CONFIGURATION ##################################################
  # base port (the lowest allowed socket number)
pyro_base_port = 7766   # (7766 is the Pyro default)
  # max number of ports starting from base port
pyro_port_range = 100 # (100 is the Pyro default)

# SUITE REGISTRATION DATABASE LOCATIONS ###############################
  # Central registrations, available to all users.
  # Specify a location relative to $CYLC_DIR for a cylc-installation
  # central database, or an external location for a central database
  # that can potentially be accessed by users of different cylc
  # installations on the same host.
central_regdb_dir = os.path.join( os.environ['CYLC_DIR'], 'CDB' )
  # Local registrations, user-specific
local_regdb_dir = os.path.join( os.environ['HOME'], '.cylc', 'LDB' )

# CONSITENCY CHECKS ###################################################
if central_regdb_dir == local_regdb_dir:
    print >> sys.stderr, "ERROR: local and central suite registration database directories" 
    print >> sys.stderr, "are identical (" + local_regdb_dir + "); they must be different."
    print >> sys.stderr, "See", \
        os.path.join( os.environ['CYLC_DIR'], 'conf', 'CylcGlobals.py' ) + '.'  
    sys.exit(1)


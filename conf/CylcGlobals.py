#!/usr/bin/env python

import os, sys

"""
MODULE FOR GLOBAL (PER CYLC INSTALLATION) CONFIGURATION DATA
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

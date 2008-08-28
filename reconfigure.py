#!/usr/bin/python

""" 
Program to "reconfigure" a running controller (get it to re-parse a
config file).  Connects via Pyro to the task_manager object, "god"
"""

import sys
import Pyro.core

# command line arguments
if len( sys.argv ) != 2:
    print "USAGE:", sys.argv[0], "<config filename>"
    sys.exit(1)
    
config_filename = sys.argv[1]

# connect to the task object inside the control program
god = Pyro.core.getProxyForURI("PYRONAME://god" )

god.parse_config_file( config_filename )

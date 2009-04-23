#!/usr/bin/pyro

# To run a Pyro nameserver in its own thread in the main program:
#import threading
#ns_starter = Pyro.naming.NameServerStarter()
#ns_thread = threading.Thread( target = ns_starter.start )
#ns_thread.setDaemon(True)
#ns_thread.start()
#ns_starter.waitUntilStarted(10)

import Pyro.core, Pyro.naming
from Pyro.errors import NamingError

import sys

def create_daemon( pyro_ns_group ):

    print " + configuring Pyro"
    # REQUIRE SINGLE THREADED OPERATION (see documentation)
    print "   - single threaded" 
    Pyro.config.PYRO_MULTITHREADED = 0

    # locate the Pyro nameserver
    print "   - locating nameserver" 
    pyro_nameserver = Pyro.naming.NameServerLocator().getNS()

    try:
	# abort if any existing objects are registered in my group name
	# (this may indicate another instance of sequenz is running
	# with the same groupname; must be unique for each instance
	# else the different systems will interfere with each other) 
    
	print "   - creating nameserver group '" + pyro_ns_group + "'"
    	pyro_nameserver.createGroup( pyro_ns_group )

    except NamingError:

	print ""
    	print "ERROR: group '" + pyro_ns_group + "' is already registered"
	
	objs = pyro_nameserver.list( pyro_ns_group )

	if len( objs ) == 0:
		print "(although it currently contains no registered objects)."

	else:
		print "And contains the following registered objects:"
		for obj in objs:
			print '  + ' + obj[0]

	print ""
	print "OPTIONS:"
	print "(i) if the group is yours from a previous aborted run you can"
	print "    manually delete it with 'pyro-nsc deletegroup " + pyro_ns_group +"'"
	print "(ii) if the group is being used by another program, change"
	print "    'pyro_ns_group' in your config file to avoid interference."
	print ""

	print "ABORTING NOW"
	#raise NamingError
	sys.exit(1)

    pyro_daemon = Pyro.core.Daemon()
    pyro_daemon.useNameServer(pyro_nameserver)

    return pyro_daemon

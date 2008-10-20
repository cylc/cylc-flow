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

import config

def create_daemon():

    # We require SINGLE THREADED operation (see repository docs)
    Pyro.config.PYRO_MULTITHREADED = 0

    # locate the Pyro nameserver
    pyro_nameserver = Pyro.naming.NameServerLocator().getNS()

    print
    print "Using Pyro nameserver group '" + config.pyro_ns_group + "'"
    print "(must be unique for each program instance)"
 
    try:
        # first delete any existing objects registered in my group name
        # (this avoids having to restart the nameserver every time we
        # run the controller, or otherwise having to disconnect
        # individual objects that already exist). 
        pyro_nameserver.deleteGroup( config.pyro_ns_group )
    except NamingError:
        # no such group already registered
        pass

    pyro_nameserver.createGroup( config.pyro_ns_group )
    pyro_daemon = Pyro.core.Daemon()
    pyro_daemon.useNameServer(pyro_nameserver)

    return pyro_daemon

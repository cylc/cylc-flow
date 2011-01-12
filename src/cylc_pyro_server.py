#!/usr/bin/pyro

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import os
import socket
import Pyro
from passphrase import passphrase

# base (lowest allowed) Pyro socket number
pyro_base_port = 7766   # (7766 is the Pyro default)

# max number of sockets starting at base
pyro_port_range = 100 # (100 is the Pyro default)

class pyro_server( object ):
    def __init__( self, suite, user=os.environ['USER'], use_passphrase=False ):

        self.suite = suite
        self.owner = user

        # REQUIRE SINGLE THREADED PYRO (see documentation)
        Pyro.config.PYRO_MULTITHREADED = 0
        # USE DNS NAMES INSTEAD OF FIXED IP ADDRESSES FROM /etc/hosts
        # (see the Userguide "Networking Issues" section).
        Pyro.config.PYRO_DNS_URI = True

        # base (lowest allowed) Pyro socket number
        Pyro.config.PYRO_PORT = pyro_base_port
        # max number of sockets starting at base
        Pyro.config.PYRO_PORT_RANGE = pyro_port_range

        Pyro.core.initServer()
        self.daemon = Pyro.core.Daemon()
        if use_passphrase:
            self.daemon.setAllowedIdentifications( [passphrase(suite).get()] )

    def shutdown( self ):
        print "Pyro daemon shutdown"
        # The True arg here results in objects being unregistered from
        # pyro-ns, which cylc no longer uses:
        self.daemon.shutdown( True )

        # If a suite shuts down via 'stop --now' or # Ctrl-C, etc., 
        # any existing client end connections will hang for a long time
        # unless we do the following (or cylc clients set a timeout,
        # presumably) which daemon.shutdown() does not do (why not?):
        self.daemon.sock.shutdown( socket.SHUT_RDWR )

    def connect( self, obj, name, qualified=True ):
        if qualified:
            qname = self.owner + '.' + self.suite + '.' + name
        else:
            qname = name
        uri = self.daemon.connect( obj, qname )

    def disconnect( self, obj ):
        self.daemon.disconnect( obj )

    def handleRequests( self, timeout=None ):
        self.daemon.handleRequests( timeout )

    def get_port( self ):
        return self.daemon.port

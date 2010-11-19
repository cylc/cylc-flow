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
import Pyro
import port_scan

class pyro_server:
    def __init__( self, suite, user=os.environ['USER'] ):

        self.suite = suite
        self.owner = user

        # REQUIRE SINGLE THREADED PYRO (see documentation)
        Pyro.config.PYRO_MULTITHREADED = 0
        # USE DNS NAMES INSTEAD OF FIXED IP ADDRESSES FROM /etc/hosts
        # (see the Userguide "Networking Issues" section).
        Pyro.config.PYRO_DNS_URI = True

        # base (lowest allowed) Pyro socket number
        Pyro.config.PYRO_PORT = port_scan.pyro_base_port
        # max number of sockets starting at base
        Pyro.config.PYRO_PORT_RANGE = port_scan.pyro_port_range

        Pyro.core.initServer()
        self.daemon = Pyro.core.Daemon()

    def shutdown( self, thing ):
        # TO DO: WHAT IS thing (T/F) ?
        print "Shutting down my Pyro daemon"
        self.daemon.shutdown( thing )

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
    

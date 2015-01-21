#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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

import sys
import socket
try:
    import Pyro
except ImportError, x:
    print >> sys.stderr, x
    sys.exit( "ERROR: Pyro is not installed" )
from passphrase import passphrase
from suite_host import get_hostname
from owner import user

class pyro_server( object ):
    def __init__( self, suite, suitedir, base_port, max_n_ports, user=user ):

        self.suite = suite
        self.owner = user

        # SINGLE THREADED PYRO
        Pyro.config.PYRO_MULTITHREADED = 1
        # USE DNS NAMES INSTEAD OF FIXED IP ADDRESSES FROM /etc/hosts
        # (see the Userguide "Networking Issues" section).
        Pyro.config.PYRO_DNS_URI = True

        # base (lowest allowed) Pyro socket number
        Pyro.config.PYRO_PORT = base_port
        # max number of sockets starting at base
        Pyro.config.PYRO_PORT_RANGE = max_n_ports

        Pyro.core.initServer()
        self.daemon = Pyro.core.Daemon()
        self.daemon.setAllowedIdentifications( [passphrase(suite,user,get_hostname()).get(suitedir=suitedir)] )

    def shutdown( self ):
        self.daemon.shutdown(True)
        # If a suite shuts down via 'stop --now' or # Ctrl-C, etc.,
        # any existing client end connections will hang for a long time
        # unless we do the following (or cylc clients set a timeout,
        # presumably) which daemon.shutdown() does not do (why not?):

        try:
            self.daemon.sock.shutdown( socket.SHUT_RDWR )
        except socket.error, x:
            print >> sys.stderr, x

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

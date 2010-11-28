#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

# LOCKSERVER CLIENT INTERFACE

import Pyro.core, Pyro.naming, Pyro.errors
import socket
from port_scan import get_port, check_port

class lockserver:
    def __init__( self, owner, host, port=None ):
        self.owner = owner
        self.host = host
        self.port = port

    def get_proxy( self ):
        if self.port:
            port = self.port
            if not check_port( "lockserver", self.owner, self.host, self.port ):
                msg = "lockserver (" + self.owner + ") not found at " + self.host + ":" + str(port)
                raise Pyro.errors.NamingError( msg )
        else:
            print "Scanning for lockserver ...",
            found, port = get_port( "lockserver", self.owner, self.host )
            if found:
                print "port", port
            else:
                print "ERROR"
                msg = "lockserver (" + self.owner + ") not found on " + self.host 
                raise Pyro.errors.NamingError( msg )

        qualified_name = self.owner + ".lockserver"
        uri = 'PYROLOC://' + self.host + ':' + str(port) + '/' + qualified_name
        self.port = port
        return Pyro.core.getProxyForURI(uri)

    def ping( self ):
        # check that a lockserver is running
        self.get_proxy()
        return self.port
        
    def get( self ):
        return self.get_proxy()

    def dump( self ):
        return self.get_proxy().dump()

    def clear( self, user ):
        return self.get_proxy().clear( user )

    def get_filenames( self ):
        return self.get_proxy().get_filenames()

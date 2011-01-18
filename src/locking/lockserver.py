#!/usr/bin/env python

# LOCKSERVER CLIENT INTERFACE

import Pyro.core, Pyro.naming, Pyro.errors
import socket
from port_scan import get_port, check_port

class lockserver(object):
    def __init__( self, owner, host, port=None ):
        self.owner = owner
        self.host = host
        self.port = port

    def get_proxy( self ):
        if self.port:
            check_port( "lockserver", self.owner, self.host, self.port )
        else:
            self.port = get_port( "lockserver", self.owner, self.host )

        qualified_name = self.owner + ".lockserver"
        uri = 'PYROLOC://' + self.host + ':' + str(self.port) + '/' + qualified_name
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

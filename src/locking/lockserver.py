#!/usr/bin/env python

# INTERFACE TO THE LOCKSERVER FOR CLIENT PROGRAMS

import Pyro.core, Pyro.naming, Pyro.errors
import socket, os
from port_scan import get_port, check_port

class lockserver(object):
    def __init__( self, host, port=None ):
        self.owner = os.environ['USER']
        self.host = host
        self.port = port

    def get_proxy( self ):
        if self.port:
            check_port( "lockserver", self.port, host=self.host )
        else:
            self.port = get_port( "lockserver", host=self.host )

        # lockservers are connected to Pyro with owner name
        # see comment in bin/_lockserver. TO DO: reuse code.
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

    def clear( self ):
        return self.get_proxy().clear()

    def get_filenames( self ):
        return self.get_proxy().get_filenames()

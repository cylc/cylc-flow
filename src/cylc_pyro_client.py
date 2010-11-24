#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import os, sys
import Pyro.core, Pyro.errors
from optparse import OptionParser
from time import sleep

class port_interrogator:
    # find which suite is running on a given port
    def __init__( self, host, port, timeout=None ):
        self.host = host
        self.port = port
        self.timeout = timeout

    def interrogate( self ):
        # get a proxy to the suite id object
        # this raises ProtocolError if connection fails
        self.proxy = Pyro.core.getProxyForURI('PYROLOC://' + self.host + ':' + str(self.port) + '/suite_id' )
        self.proxy._setTimeout(self.timeout)
        # this raises a TimeoutError if the connection times out
        return self.proxy.id()

class client:
    def __init__( self, suite, owner, host, port ):
        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port

    def get_proxy( self, target ):
        # get a pyro proxy for the target object
        objname = self.owner + '.' + self.suite + '.' + target
        return Pyro.core.getProxyForURI('PYROLOC://' + self.host + ':' + str(self.port) + '/' + objname )

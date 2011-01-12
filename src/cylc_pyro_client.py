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
from passphrase import passphrase
from port_scan import get_port, check_port

class client( object ):
    def __init__( self, suite, owner, host, port ):
        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port
        try:
            self.passphrase = passphrase( suite )
        except:
            self.passphrase = None

    def get_proxy( self, target, silent=False ):
        # callers need to check for port_scan.SuiteIdentificationError:
        if self.port:
            check_port( self.suite, self.owner, self.host, self.port, self.passphrase )
        else:
            self.port = get_port( self.suite, self.owner, self.host, self.passphrase )

        # get a pyro proxy for the target object
        objname = self.owner + '.' + self.suite + '.' + target

        uri = 'PYROLOC://' + self.host + ':' + str(self.port) + '/' + objname 
        # callers need to check for Pyro.NamingError if target object not found:
        proxy = Pyro.core.getProxyForURI(uri)

        # set set passphrase if necessary:
        if self.passphrase:
            proxy._setIdentification( self.passphrase )

        return proxy

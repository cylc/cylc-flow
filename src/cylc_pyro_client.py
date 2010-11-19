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

def ping( host, port ):
    proxy = Pyro.core.getProxyForURI('PYROLOC://' + host + ':' + str(port) + '/ping' )
    return proxy.identify()

class client:
    def __init__( self, suite, owner, host, port ):
        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port

    def get_proxy( self, target ):
        # attempt to get a pyro proxy for the target object
        objname = self.owner + '.' + self.suite + '.' + target
        #try:
        target = Pyro.core.getProxyForURI('PYROLOC://' + self.host + ':' + str(self.port) + '/' + objname )
        #except Pyro.errors.NamingError:
        #    # THIS IMPLIES self.group IS NOT RUNNING
        #    # OR NO SUCH suite OBJECT IS REGISTERED.
        #    raise SystemExit( 
        #            'ERROR: failed to get a pyro proxy for ' + target + ' in ' + self.group + \
        #            '\n => suite not running?')
        #except Exception, x:
        #    # THIS SHOULD NOT BE REACHED
        #    print group + ' is PROBABLY NOT running'
        #    print '  (but an unexpected error occurred trying to get the pyro proxy: '
        #    print x
        #    sys.exit(1)

        return target

# NOTES-----------------------------------------------------------------------:
# Pyro.errors.ProtocolError:
# retry if temporary network problems prevented connection?

# http://pyro.sourceforge.net/manual/10-errors.html
# Exception: ProtocolError,
#    Error string: connection failed
#    Raised by: bindToURI method of PYROAdapter
#    Description: Network problems caused the connection to fail.
#                 Also the Pyro server may have crashed.
#                 (presumably after connection established - hjo)

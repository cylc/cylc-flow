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
import cylc_pyro_ns

class client:
    def __init__( self, host, group ):
        self.host = host
        self.group = group

    def ping( self ):
        # Check the target system is running by attempting to contact
        # and then interact with its minimal life indicator object.
        # If this works client commands don't need to catch exceptions?

        lifeline = self.get_proxy( 'minimal' )

        try:
            result = lifeline.live()
        except Pyro.errors.ProtocolError:
            print 'ERROR: ' + self.group + ' is NOT RUNNING'
            print '  But it IS registered with the Pyro Nameserver, which implies'
            print '  that the system has previously exited without cleaning up.'
            print '  To clean up manually:'
            print '     $ pyro-nsc deletegroup ' + group
            sys.exit(1)
        except Exception, x:
            # THIS SHOULD NOT BE REACHED
            print 'ERROR: ' + self.group + ' is PROBABLY NOT RUNNING'
            print '  But it IS registered with the Pyro Nameserver, which implies'
            print '  that the system has previously exited without cleaning up.'
            print '  HOWEVER: an unexpected error occurred:', x
            print '  Manual cleanup:'
            print '     $ pyro-nsc deletegroup ' + group
            sys.exit(1)
 
    def get_proxy( self, target ):
        # check nameserver is running (aborts if none found)
        cylc_pyro_ns.ns( self.host )

        # attempt to get a pyro proxy for the target object
        try:
            target = Pyro.core.getProxyForURI('PYRONAME://' + self.host + '/' + self.group + '.' + target )
        except Pyro.errors.NamingError:
            # THIS IMPLIES self.group IS NOT RUNNING
            # OR NO SUCH SYSTEM OBJECT IS REGISTERED.
            raise SystemExit( 
                    'ERROR: failed to get a pyro proxy for ' + target + ' in ' + self.group + \
                    '\n => system not running, or system object not registered with Pyro.')
        except Exception, x:
            # THIS SHOULD NOT BE REACHED
            print group + ' is PROBABLY NOT running'
            print '  (but an unexpected error occurred trying to get the pyro proxy: '
            print x
            sys.exit(1)

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

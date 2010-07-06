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
import Pyro.core
from Pyro.errors import PyroError,NamingError,ProtocolError
from optparse import OptionParser
from time import sleep
import cylc_pyro_ns

class connector:
    def __init__( self, hostname, groupname, target, silent=False, check=True ):
        self.target = target
        self.hostname = hostname
        self.groupname = groupname

        if check:
            foo = cylc_pyro_ns.ns( hostname )
            if not foo.registered( groupname ):
                msg = "WARNING: no Pyro objects registered under", groupname 
                if not silent:
                    print msg
                    # print existing groups and exit
                    print
                    foo.print_info()
                    print
                raise SystemExit( msg )

    def get( self ):
        try:
            target = Pyro.core.getProxyForURI('PYRONAME://' + self.hostname + '/' + self.groupname + '.' + self.target )
        except:
            raise
        else:
            return target

        #except ProtocolError, x:
            # retry if temporary network problems prevented connection

            # TO DO: do we need to single out just the 'connection failed error?'
            # TO DO: WRAP IN A RETRY LOOP FOR TEMPORARY NETWORK PROBLEMS?

            # http://pyro.sourceforge.net/manual/10-errors.html
            # Exception: ProtocolError,
            #    Error string: connection failed
            #    Raised by: bindToURI method of PYROAdapter
            #    Description: Network problems caused the connection to fail.
            #                 Also the Pyro server may have crashed.
            #                 (presumably after connection established - hjo)

            #raise SystemExit( x )
        #    raise

        #except NamingError, x:
            #print "\n\033[1;37;41m" + x + "\033[0m"
            #print x
            #raise SystemExit( "ERROR" )
        #    raise

        #except Exception, x:
            #raise SystemExit( x )
        #    raise

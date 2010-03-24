#!/usr/bin/python

import os, sys
import Pyro.core
from Pyro.errors import PyroError,NamingError,ProtocolError
from optparse import OptionParser
from time import sleep
import pyrex

class connector:

    def __init__( self, hostname, groupname, target ):

        self.target = target
        self.hostname = hostname
        self.groupname = groupname

        foo = pyrex.discover( hostname )

        if not foo.registered( groupname ):
            print "WARNING: no " + groupname + " registered ..." 
            # print available systems and exit
            print
            foo.print_info()
            print
            sys.exit(1)

    def get( self ):
        try:
            target = Pyro.core.getProxyForURI('PYRONAME://' + self.hostname + '/' + self.groupname + '.' + self.target )

        except ProtocolError, x:
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

            raise SystemExit( x )

        except NamingError, x:
            #print "\n\033[1;37;41m" + x + "\033[0m"
            print x
            raise SystemExit( "ERROR" )

        except Exception, x:
            raise SystemExit( x )

        return target

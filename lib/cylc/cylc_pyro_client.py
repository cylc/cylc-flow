#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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

import os, sys
import Pyro.core, Pyro.errors
from optparse import OptionParser
from hostname import hostname
from time import sleep
from passphrase import passphrase, PassphraseNotFoundError, SecurityError
from port_scan import get_port, check_port

class client( object ):
    def __init__( self, suite, owner=os.environ['USER'], host=hostname, port=None ):
        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port

        self.passphrase = None
        try:
            self.passphrase = passphrase( suite ).get()
        except PassphraseNotFoundError:
            # assume this means the suite requires no passphrase
            pass
        except SecurityError,x:
            print "WARNING: There is a problem with the secure passphrase for suite " + suite + ":"
            print x
            print "Continuing, but access will be denied if the suite requires a passphrase."

    def get_proxy( self, target ):
        # callers need to check for port_scan.SuiteIdentificationError:
        if self.port:
            check_port( self.suite, self.port, self.owner, self.host, silent=True )
        else:
            self.port = get_port( self.suite, self.owner, self.host, silent=True, pphrase=self.passphrase )

        # get a pyro proxy for the target object
        objname = self.owner + '.' + self.suite + '.' + target

        uri = 'PYROLOC://' + self.host + ':' + str(self.port) + '/' + objname 
        # callers need to check for Pyro.NamingError if target object not found:
        proxy = Pyro.core.getProxyForURI(uri)

        # set set passphrase if necessary:
        if self.passphrase:
            proxy._setIdentification( self.passphrase )

        return proxy

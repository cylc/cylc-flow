#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

try:
    import Pyro.core
except ImportError, x:
    raise SystemExit("ERROR: Pyro is not installed")

import sys
from optparse import OptionParser
from hostname import hostname
from time import sleep
from port_scan import get_port, check_port
from passphrase import passphrase
from owner import user

class client( object ):
    def __init__( self, suite, pphrase=None, owner=user, host=hostname, pyro_timeout=None, port=None, verbose=False ):
        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port
        self.verbose = verbose
        if pyro_timeout:
            self.pyro_timeout = float(pyro_timeout)
        else:
            self.pyro_timeout = None

        #if pphrase:
        self.pphrase = pphrase
        #else:
        #    # TO DO: IS THIS NECESSARY - called from gcylc
        #    # get the suite passphrase
        #    self.pphrase = passphrase( suite, owner, host).get( None, None )

    def get_proxy( self, target ):
        # callers need to check for port_scan.SuiteIdentificationError:
        if self.port:
            check_port( self.suite, self.pphrase, self.port, self.owner, self.host, self.pyro_timeout, self.verbose )
        else:
            self.port = get_port( self.suite, self.owner, self.host, self.pphrase, self.pyro_timeout, self.verbose )

        # get a pyro proxy for the target object
        objname = self.owner + '.' + self.suite + '.' + target

        uri = 'PYROLOC://' + self.host + ':' + str(self.port) + '/' + objname 
        # callers need to check for Pyro.NamingError if target object not found:
        proxy = Pyro.core.getProxyForURI(uri)

        # set set passphrase if necessary:
        if self.pphrase:
            proxy._setIdentification( self.pphrase )

        return proxy


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

# INTERFACE TO THE LOCKSERVER FOR CLIENT PROGRAMS

import Pyro.core, Pyro.naming, Pyro.errors
import socket
from cylc.owner import user
from cylc.port_scan import get_port, check_port

class lockserver(object):
    def __init__( self, host, owner=user, port=None, timeout=None ):
        self.owner = owner
        self.host = host
        self.port = port
        if timeout:
            self.timeout = float(timeout)
        else:
            self.timeout = None

    def get_proxy( self ):
        if self.port:
            check_port( "lockserver", None, self.port, self.owner, self.host, self.timeout )
        else:
            self.port = get_port( "lockserver", self.owner, self.host, None, self.timeout )

        # lockservers are connected to Pyro with owner name
        # see comment in bin/_lockserver. TO DO: reuse code.
        qualified_name = self.owner + ".lockserver"
        uri = 'PYROLOC://' + self.host + ':' + str(self.port) + '/' + qualified_name
        return Pyro.core.getProxyForURI(uri)

    def get_port( self ):
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

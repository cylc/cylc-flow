#!/usr/bin/pyro

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import Pyro.errors, Pyro.core
from cylc_pyro_server import pyro_base_port, pyro_port_range

class port_interrogator:
    # find which suite or lockserver is running on a given port
    def __init__( self, host, port, timeout=None ):
        self.host = host
        self.port = port
        self.timeout = timeout

    def interrogate( self ):
        # get a proxy to the cylcid object
        # this raises ProtocolError if connection fails
        uri = 'PYROLOC://' + self.host + ':' + str(self.port) + '/cylcid' 
        self.proxy = Pyro.core.getProxyForURI(uri)
        self.proxy._setTimeout(self.timeout)
        # this raises a TimeoutError if the connection times out
        return self.proxy.id()

def get_port( name, owner, host ):
    found = False
    port = 0
    for p in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        try:
            one, two = port_interrogator( host, p ).interrogate()
        except Pyro.errors.ProtocolError:
            # connection failed: no pyro server listening at this port
            pass
        except Pyro.errors.NamingError:
            # pyro server here, but it's not a cylc suite or lockserver
            pass
        else:
            if one == name and two == owner:
                found = True
                port = p
                break
    return ( found, port )    

def check_port( name, owner, host, port ):
    # is name,owner running at host:port?
    try:
        one, two = port_interrogator( host, port ).interrogate() 
    except Pyro.errors.ProtocolError:
        # no cylc suite at port
        return False
    else:
        if one == name and two == owner:
            return True
        else:
            return False
 
def scan( host ):
    names = []
    for port in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        try:
            name, owner = port_interrogator( host, port ).interrogate()
        except Pyro.errors.ProtocolError:
            # connection failed: no pyro server listening at this port
            pass
        except Pyro.errors.NamingError:
            # pyro server here, but it's not a cylc suite or lockserver
            pass
        else:
            names.append( ( name, owner, port ) )

    return names

#!/usr/bin/pyro

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import os
import Pyro.errors, Pyro.core
from cylc_pyro_server import pyro_base_port, pyro_port_range

class SuiteIdentificationError( Exception ):
    """
    Attributes: None
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class ConnectionDeniedError( SuiteIdentificationError ):
    pass

class NoSuiteFoundError( SuiteIdentificationError ):
    pass

class SuiteNotFoundError( SuiteIdentificationError ):
    pass

class OtherSuiteFoundError( SuiteIdentificationError ):
    pass

class OtherServerFoundError( SuiteIdentificationError ):
    pass

class port_interrogator(object):
    # find which suite or lockserver is running on a given port
    def __init__( self, host, port, timeout=None, passphrase=None ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.passphrase = passphrase

    def interrogate( self ):
        # get a proxy to the cylcid object
        # this raises ProtocolError if connection fails
        uri = 'PYROLOC://' + self.host + ':' + str(self.port) + '/cylcid' 
        self.proxy = Pyro.core.getProxyForURI(uri)
        self.proxy._setTimeout(self.timeout)
        if self.passphrase:
            self.proxy._setIdentification( self.passphrase )
        # this raises a TimeoutError if the connection times out
        return self.proxy.id()

def portid( host, port ):
    return host + ":" + str(port)

def suiteid( name, owner, host, port ):
    return "[" + name + "] " + owner + "@" + portid( host,port)

def get_port( name, owner, host, passphrase=None ):
    # Scan ports until a particular suite is found.
    # - Ignore ports at which no suite is found.
    # - Print denied connections (secure passphrase required).
    # - Print non-cylc pyro servers found
    found = False
    for port in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        try:
            one, two = port_interrogator( host, port, passphrase=passphrase ).interrogate()
        except Pyro.errors.ConnectionDeniedError:
            print "Connection Denied at " + portid( host, port )
        except Pyro.errors.ProtocolError:
            pass
            #print "No Suite Found at " + portid( host, port )
        except Pyro.errors.NamingError:
            print "Non-cylc pyro server found at " + portid( host, port )
        else:
            if one == name and two == owner:
                print suiteid( name, owner, host, port )
                return port

    raise SuiteNotFoundError, "ERROR: Suite not found at " + host

def check_port( name, owner, host, port, passphrase=None ):
    # is name,owner running at host:port?
    try:
        one, two = port_interrogator( host, port, passphrase=passphrase ).interrogate() 
    except Pyro.errors.ConnectionDeniedError:
        raise ConnectionDeniedError, "ERROR: Connection Denied  at " + portid( host, port )
    except Pyro.errors.ProtocolError:
        raise NoSuiteFoundError, "ERROR: No suite found at host:port"
    except Pyro.errors.NamingError:
        raise OtherServerFoundError, "ERROR: non-cylc pyro server found at " + portid( host, port )
    else:
        if one == name and two == owner:
            print suiteid( name, owner, host, port )
            return True
        else:
            raise OtherSuiteFoundError, "ERROR: Found " + suiteid( one, two, host, port )
 
def scan( host, passphrase=None, verbose=True ):
    # scan all cylc Pyro ports for cylc suites, and return results
    suites = []
    for port in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        try:
            name, owner = port_interrogator( host, port, passphrase=passphrase ).interrogate()
        except Pyro.errors.ConnectionDeniedError:
            print "Connection Denied at " + portid( host, port )
        except Pyro.errors.ProtocolError:
            pass
            #print "No Suite Found at " + portid( host, port )
        except Pyro.errors.NamingError:
            print "Non-cylc pyro server found at " + portid( host, port )
        else:
            if verbose:
                print suiteid( name, owner, host, port )
            # found a cylc suite or lock server
            suites.append( ( name, owner, port ) )

    return suites

def scan_my_suites( host ):
    suites = []
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
            if name != 'lockserver' and owner == os.environ['USER']:
                suites.append( ( name, port ) )
    return suites

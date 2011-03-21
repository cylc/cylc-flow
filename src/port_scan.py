#!/usr/bin/pyro

from registration import localdb
from passphrase import passphrase as pphrase
import os
#from time import sleep
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
    def __init__( self, host, port, my_passphrases=None, timeout=None ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.my_passphrases = my_passphrases
        self.me = os.environ['USER']

    def interrogate( self ):
        # get a proxy to the cylcid object
        # this raises ProtocolError if connection fails
        uri = 'PYROLOC://' + self.host + ':' + str(self.port) + '/cylcid' 
        self.proxy = Pyro.core.getProxyForURI(uri)
        self.proxy._setTimeout(self.timeout)

        # note: get a TimeoutError if the connection times out

        # first try access with no passphrase
        name = owner = None
        try:
            name, owner = self.proxy.id()
        except Pyro.errors.ConnectionDeniedError, x:
            # must be a secure suite, try my passphrases
            if not self.my_passphrases:
                raise
            for reg in self.my_passphrases:
                self.proxy._setIdentification( self.my_passphrases[reg] )
                try:
                    name, owner = self.proxy.id()
                except:
                    # denied, try next passphrase
                    continue
                else:
                    # got access
                    if name == reg and owner == self.me:
                        return name, owner, 'secure'
                    else:
                        # this indicates that one of my suites has an
                        # identical passphrase to this other suite.
                        raise Pyro.errors.ConnectionDeniedError, x
                
            # loop end without returning ID => all of my passphrases denied
            raise Pyro.errors.ConnectionDeniedError, x
        except:
            # another error (other than ConnectionDenied)
            raise
        else:
            # got access with no passphrase => not a secure suite
            return name, owner, 'insecure'

def portid( host, port ):
    return host + ":" + str(port)

def suiteid( name, owner, host, port=None ):
    if port != None:
        res = "[" + name + "] " + owner + "@" + portid( host,port)
    else:
        res = "[" + name + "] " + owner + "@" + host
    return res

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
            #print "No Suite Found at " + portid( host, port )
            pass
        except Pyro.errors.NamingError:
            print "Non-cylc pyro server found at " + portid( host, port )
        else:
            #print one, two
            #print name, owner
            if one == name and two == owner:
                print suiteid( name, owner, host, port )
                return port
    raise SuiteNotFoundError, "ERROR: suite not found: " + suiteid( name, owner, host )

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
            raise OtherSuiteFoundError, "ERROR: Found " + suiteid( one, two, host, port ) + ' NOT ' + suiteid( name, owner, host, port )
 
def scan( host, verbose=True ):
    # scan all cylc Pyro ports for cylc suites

    # load my passphrases in case any secure suites are encountered in the scan.
    reg = localdb()
    reg.load_from_file()
    reg_suites = reg.get_list(name_only=True)
    my_passphrases = {}
    for reg in reg_suites:
        try:
            # in case one is using a secure passphrase
            pp = pphrase( reg ).get()
        except:
            # we have no passphrase defined for this suite
            pass
        else:
            my_passphrases[ reg ] = pp

    suites = []
    for port in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        try:
            name, owner, security = port_interrogator( host, port, my_passphrases ).interrogate()
        except Pyro.errors.ConnectionDeniedError:
            print "Connection Denied at " + portid( host, port )
        except Pyro.errors.ProtocolError:
            #print "No Suite Found at " + portid( host, port )
            pass
        except Pyro.errors.NamingError:
            print "Non-cylc pyro server found at " + portid( host, port )
        else:
            if verbose:
                if security == 'secure':
                    print suiteid( name, owner, host, port ), security
                else:
                    print suiteid( name, owner, host, port )
            # found a cylc suite or lock server
            suites.append( ( name, owner, port ) )
    return suites

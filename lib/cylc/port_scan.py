#!/usr/bin/pyro

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

import os
from hostname import hostname
from registration import localdb
from passphrase import passphrase
import Pyro.errors, Pyro.core
from conf.CylcGlobals import pyro_base_port, pyro_port_range

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
                        continue
                
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

def cylcid_uri( host, port ):
    return 'PYROLOC://' + host + ':' + str(port) + '/cylcid' 

def get_port( suite, owner=os.environ['USER'], host=hostname, pphrase=None, timeout=None, silent=False ):
    # Scan ports until a particular suite is found.

    # does this suite have a secure passphrase defined?
    if not pphrase:
        try:
            pphrase = passphrase( suite ).get()
        except:
            pphrase = None

    for port in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        uri = cylcid_uri( host, port )
        proxy = Pyro.core.getProxyForURI(uri)
        proxy._setTimeout(timeout)
        # note: we'll get a TimeoutError if the connection times out

        # Giving the suite passphrase does not result in connection
        # denied if the suite is currently not using its passphrase
        proxy._setIdentification( pphrase )

        try:
            name, xowner = proxy.id()
        except Pyro.errors.ConnectionDeniedError:
            #print "Wrong suite or wrong passphrase at " + portid( host, port )
            pass
        except Pyro.errors.ProtocolError:
            #print "No Suite Found at " + portid( host, port )
            pass
        except Pyro.errors.NamingError:
            #print "Non-cylc pyro server found at " + portid( host, port )
            pass
        else:
            if name == suite and xowner == owner:
                if not silent:
                    print suiteid( suite, owner, host, port )
                # RESULT
                return port
            else:
                # ID'd some other suite.
                #print 'OTHER SUITE:', suiteid( name, xowner, host, port )
                pass
    raise SuiteNotFoundError, "Suite not running: " + suiteid( suite, owner, host )

def check_port( suite, port, owner=os.environ['USER'], host=hostname, timeout=None, silent=False ):
    # is a particular suite running at host:port?

    # does this suite have a secure passphrase defined?
    try:
        pphrase = passphrase( suite ).get()
    except:
        pphrase = None

    uri = cylcid_uri( host, port )
    proxy = Pyro.core.getProxyForURI(uri)
    proxy._setTimeout(timeout)
    # note: we'll get a TimeoutError if the connection times out

    # Giving the suite passphrase does not result in connection
    # denied if the suite is currently not using its passphrase
    proxy._setIdentification( pphrase )

    try:
        name, xowner = proxy.id()
    except Pyro.errors.ConnectionDeniedError:
        raise ConnectionDeniedError, "ERROR: Connection Denied  at " + portid( host, port )
    except Pyro.errors.ProtocolError:
        raise NoSuiteFoundError, "ERROR: " + suite + " not found at " + portid( host, port )
    except Pyro.errors.NamingError:
        raise OtherServerFoundError, "ERROR: non-cylc pyro server found at " + portid( host, port )
    else:
        if name == suite and xowner == owner:
            if not silent:
                print suiteid( suite, owner, host, port )
            # RESULT
            return True
        else:
            # ID'd some other suite.
            raise OtherSuiteFoundError, "ERROR: Found " + suiteid( name, xowner, host, port ) + ' NOT ' + suiteid( suite, owner, host, port )

def scan( host, verbose=True, mine=False, silent=False ):
    # scan all cylc Pyro ports for cylc suites
    me = os.environ['USER']

    # load my passphrases in case any secure suites are encountered in the scan.
    reg = localdb()
    reg.load_from_file()
    #reg_suites = reg.get_list(name_only=True)
    reg_suites = reg.get_list()
    my_passphrases = {}
    for rg in reg_suites:
        try:
            # in case one is using a secure passphrase
            pp = passphrase( rg ).get()
        except:
            # we have no passphrase defined for this suite
            pass
        else:
            my_passphrases[ rg ] = pp

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
                    if not silent:
                        print suiteid( name, owner, host, port ), security
                else:
                    if not silent:
                        print suiteid( name, owner, host, port )
            # found a cylc suite or lock server
            if mine:
                if owner == me:
                    suites.append( ( name, port ) )
            else:
                suites.append( ( name, owner, port ) )
    return suites

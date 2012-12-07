#!/usr/bin/pyro

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

import os, sys
from suite_host import hostname
from owner import user
from passphrase import passphrase
from registration import localdb
import datetime
import Pyro.errors, Pyro.core
from global_config import globalcfg

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

class ConnectionTimedOutError( SuiteIdentificationError ):
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
    def __init__( self, host, port, my_passphrases=None, pyro_timeout=None ):
        self.host = host
        self.port = port
        if pyro_timeout: # convert from string
            self.pyro_timeout = float(pyro_timeout)
        else:
            self.pyro_timeout = None
        self.my_passphrases = my_passphrases

    def interrogate( self ):
        # get a proxy to the cylcid object
        # this raises ProtocolError if connection fails
        uri = 'PYROLOC://' + self.host + ':' + str(self.port) + '/cylcid' 
        self.proxy = Pyro.core.getProxyForURI(uri)
        self.proxy._setTimeout(self.pyro_timeout)

        # first try access with no passphrase
        name = owner = None
        try:
            # (caller handles TimeoutError)
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
                    if name == reg and owner == user:
                        return name, owner, 'secure'
                    else:
                        # this indicates that one of my suites has an
                        # identical passphrase to this other suite.
                        continue

            # loop end without returning ID => all of my passphrases denied
            raise Pyro.errors.ConnectionDeniedError, x
        except:
            raise
        else:
            # got access with no passphrase => not a secure suite
            # TO DO: THIS IS NO LONGER LEGAL from cylc-4.5.0
            return name, owner, 'insecure'

def warn_timeout( host, port, timeout ):
    print >> sys.stderr, "WARNING: connection timed out (" + str(timeout) + "s) at", portid( host, port )
    #print >> sys.stderr, '  This could mean a Ctrl-Z stopped suite or similar is holding up the port,'
    #print >> sys.stderr, '  or your pyro connection timeout needs to be longer than', str(timeout), 'seconds.'

def portid( host, port ):
    return host + ":" + str(port)

# old complex output format for scan command etc.: '[suite] owner@host:port'
# new simple output format is: 'suite owner host port' - better for parsing.
##def suiteid( name, owner, host, port=None ):
##    if port != None:
##        res = "[" + name + "] " + owner + "@" + portid( host,port)
##    else:
##        res = "[" + name + "] " + owner + "@" + host
##    return res

def cylcid_uri( host, port ):
    return 'PYROLOC://' + host + ':' + str(port) + '/cylcid' 

def get_port( suite, owner=user, host=hostname, pphrase=None, pyro_timeout=None, verbose=False ):
    # Scan ports until a particular suite is found.

    globals = globalcfg()
    pyro_base_port = globals.cfg['pyro']['base port']
    pyro_port_range = globals.cfg['pyro']['maximum number of ports']

    for port in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        uri = cylcid_uri( host, port )
        try:
            proxy = Pyro.core.getProxyForURI(uri)
        except Pyro.errors.URIError, x:
            # No such host?
            raise SuiteNotFoundError, x

        if pyro_timeout: # convert from string
            pyro_timeout = float( pyro_timeout )

        proxy._setTimeout(pyro_timeout)
        proxy._setIdentification( pphrase )

        before = datetime.datetime.now()
        try:
            name, xowner = proxy.id()
        except Pyro.errors.TimeoutError:
            warn_timeout( host, port, pyro_timeout )
            pass
        except Pyro.errors.ConnectionDeniedError:
            #print >> sys.stderr, "Wrong suite or wrong passphrase at " + portid( host, port )
            pass
        except Pyro.errors.ProtocolError:
            #print >> sys.stderr, "No Suite Found at " + portid( host, port )
            pass
        except Pyro.errors.NamingError:
            #print >> sys.stderr, "Non-cylc pyro server found at " + portid( host, port )
            pass
        else:
            if verbose:
                after = datetime.datetime.now()
                print "Pyro connection on port " +str(port) + " took: " + str( after - before )
            if name == suite and xowner == owner:
                if verbose:
                    print suite, owner, host, port
                # RESULT
                return port
            else:
                # ID'd some other suite.
                #print 'OTHER SUITE:', name, xowner, host, port
                pass
    raise SuiteNotFoundError, "Suite not running: " + suite + ' ' + owner + ' ' + host

def check_port( suite, pphrase, port, owner=user, host=hostname, pyro_timeout=None, verbose=False ):
    # is a particular suite running at host:port?

    uri = cylcid_uri( host, port )
    proxy = Pyro.core.getProxyForURI(uri)
    if pyro_timeout: # convert from string
        pyro_timeout = float(pyro_timeout)
    proxy._setTimeout(pyro_timeout)

    proxy._setIdentification( pphrase )

    before = datetime.datetime.now()
    try:
        name, xowner = proxy.id()
    except Pyro.errors.TimeoutError:
        warn_timeout( host, port, pyro_timeout )
        raise ConnectionTimedOutError, "ERROR, Connection Timed Out " + portid( host, port )
    except Pyro.errors.ConnectionDeniedError:
        raise ConnectionDeniedError, "ERROR: Connection Denied  at " + portid( host, port )
    except Pyro.errors.ProtocolError:
        raise NoSuiteFoundError, "ERROR: " + suite + " not found at " + portid( host, port )
    except Pyro.errors.NamingError:
        raise OtherServerFoundError, "ERROR: non-cylc pyro server found at " + portid( host, port )
    else:
        if verbose:
            after = datetime.datetime.now()
            print "Pyro connection on port " +str(port) + " took: " + str( after - before )
        if name == suite and xowner == owner:
            # RESULT
            if verbose:
                print suite, owner, host, port
            return True
        else:
            # ID'd some other suite.
            print >> sys.stderr, 'Found ' + name + ' ' + xowner + ' ' + host + ' ' + port
            print >> sys.stderr, ' NOT ' + suite + ' ' + owner + ' ' + host + ' ' + port
            raise OtherSuiteFoundError, "ERROR: Found another suite"

def scan( host=hostname, db=None, pyro_timeout=None, verbose=False, silent=False ):
    #print 'SCANNING PORTS'
    # scan all cylc Pyro ports for cylc suites

    globals = globalcfg()
    pyro_base_port = globals.cfg['pyro']['base port']
    pyro_port_range = globals.cfg['pyro']['maximum number of ports']

    # In non-verbose mode print nothing (scan is used by cylc db viewer).

    # load my suite passphrases 
    reg = localdb(db)
    reg.load_from_file()
    reg_suites = reg.get_list()
    my_passphrases = {}
    for item in reg_suites:
        rg = item[0]
        di = item[1]
        try:
            pp = passphrase( rg, user, host ).get( suitedir=di )
        except Exception, x:
            #print >> sys.stderr, x
            # no passphrase defined for this suite
            pass
        else:
            my_passphrases[ rg ] = pp

    suites = []
    for port in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        before = datetime.datetime.now()
        try:
            name, owner, security = port_interrogator( host, port, my_passphrases, pyro_timeout ).interrogate()
        except Pyro.errors.TimeoutError:
            warn_timeout( host, port, pyro_timeout )
            pass
        except Pyro.errors.ConnectionDeniedError:
            # secure suite
            if verbose:
                print >> sys.stderr, "Connection Denied at " + portid( host, port )
        except Pyro.errors.ProtocolError:
            # no suite
            #if verbose:
            #    print >> sys.stderr, "No Suite Found at " + portid( host, port )
            pass
        except Pyro.errors.NamingError:
            # other Pyro server
            if verbose:
                print >> sys.stderr, "Non-cylc Pyro server found at " + portid( host, port )
        except:
            raise
        else:
            if not silent:
                # used by cylc db viewer scanning for running suites
                print name, owner, host, port
            if verbose:
                after = datetime.datetime.now()
                print "Pyro connection on port " +str(port) + " took: " + str( after - before )
            # found a cylc suite or lock server
            suites.append( ( name, port ) )
    return suites


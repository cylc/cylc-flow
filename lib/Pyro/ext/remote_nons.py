#############################################################################
#  
#	simple Pyro connection module, without requiring Pyro's NameServer
#	(adapted from John Wiegley's remote.py)
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import signal
import sys
import time

import Pyro.errors
import Pyro.naming
import Pyro.core
import Pyro.util

true, false = 1, 0

verbose            = false
pyro_daemon        = None
client_initialized = false
server_initialized = false
daemon_objects     = []

from Pyro.protocol import ProtocolError


def get_server_object(objectName, hostname , portnum):
    global client_initialized

    # initialize Pyro -- Python Remote Objects
    if not client_initialized:
        Pyro.core.initClient(verbose)
        client_initialized = true


    if verbose:
        print 'Binding object %s' % objectName

    try:
        URI = 'PYROLOC://%s:%d/%s' % (hostname,portnum,objectName)
        if verbose:
            print 'URI:', URI

        return Pyro.core.getAttrProxyForURI(URI)

    except Pyro.core.PyroError, x:
        raise Pyro.core.PyroError("Couldn't bind object, Pyro says:", x)

def provide_server_object(obj, name = None, hostname = '', portnum = None):
    global server_initialized, pyro_daemon
    proxy_class = Pyro.core.DynamicProxyWithAttrs

    if not server_initialized:
        Pyro.core.initServer(verbose)
        server_initialized = true

    if pyro_daemon is None:
        pyro_daemon = Pyro.core.Daemon(host = hostname, port = portnum)


    if not isinstance(obj, Pyro.core.ObjBase):
        slave = Pyro.core.ObjBase()
        slave.delegateTo(obj)
        obj = slave

    URI = pyro_daemon.connect(obj, name)
    if verbose:
        print 'provide_server_object: URI = ', URI
    daemon_objects.append(obj)

    proxy = proxy_class(URI)

    return proxy

abort = false

def interrupt(*args):
	global abort
	abort = true

if hasattr(signal,'SIGINT'): signal.signal(signal.SIGINT, interrupt)
#if hasattr(signal,'SIGHUP'): signal.signal(signal.SIGHUP, interrupt)
#if hasattr(signal,'SIGQUIT'): signal.signal(signal.SIGQUIT, interrupt)

def handle_requests(wait_time = None, callback = None):
    global abort
    
    abort = false

    if pyro_daemon is None:
        raise Pyro.errors.PyroError("There is no daemon with which to handle requests")
        return

    if wait_time:
        start = time.time()

    while not abort:
        try:
            pyro_daemon.handleRequests(wait_time)
            if wait_time:
                now = time.time()
                if callback and now - start > wait_time:
                    callback()
                    start = now
                elif callback:
                    callback()

        except Exception, msg:
            if verbose:
                print "Error:", sys.exc_type, msg
            abort = true
        except:
            abort = true

    return abort

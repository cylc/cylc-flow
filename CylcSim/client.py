#!/usr/bin/env python

import os, sys
import Pyro.core


def get_proxy( name, host, port ):
    try:
        return Pyro.core.getProxyForURI("PYROLOC://" + host + ":" + port + "/" +name )
    except Pyro.errors.URIError, x:
        raise SystemExit( 'getProxyForURI URI ERROR, ' + host + ': ' + str(x) )
    except Exception, x:
        raise SystemExit( 'ERROR: ' + str(x) )

def spam_server( port, host='localhost' ):
    reporter = get_proxy( 'reporter', host, port )
    n_tasks = reporter.get_n()
    task_proxies = []
    for i in range( 0, n_tasks ):
        proxy = get_proxy( 'Task' + str(i), host, port )
        task_proxies.append( proxy )

    for count in range( 0, 10 ):
        for tp in task_proxies:
            tp.incoming( 'hello ' + str(count) )
        count +=1

if len(sys.argv) != 2:
    print "USAGE: client.py PORT"
    sys.exit(1)

port = sys.argv[1]

try:
    spam_server( port )
except Pyro.errors.ProtocolError, x:
    # Examples:
    # 1/ "connection failed" => no pyro server at this port
    # 2/ "incompatible protocol version => non-pyro server found (e.g.
    #    ssh at port 22)
    raise SystemExit( 'Call via Pyro Proxy: Protocol ERROR, ' + str(x) )
except Pyro.errors.NamingError, x:
    # Example:
    # ("no object found by this name", "report"):
    # A pyro server (the intended one OR another one) but the requested
    # object is not registered by it
    raise SystemExit( 'Call via Pyro Proxy: Naming ERROR, ' + str(x) )
except Exception, x:
    raise SystemExit( 'Call via Pyro Proxy: ERROR, ' + str(x) )


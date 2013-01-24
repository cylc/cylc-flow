#!/usr/bin/env python

# See CommsTest/README

import os, sys
import Pyro.core

if len(sys.argv) != 3:
    print "USAGE: CommsTestClient.py HOST PORT"
    sys.exit(1)

host = sys.argv[1]
port = sys.argv[2]

try:
    proxy = Pyro.core.getProxyForURI("PYROLOC://" + host + ":" + port + "/report")
except Pyro.errors.URIError, x:
    raise SystemExit( 'getProxyForURI URI ERROR, ' + host + ': ' + str(x) )
except Exception, x:
    raise SystemExit( 'ERROR: ' + str(x) )

try:
    print proxy.get_report( os.environ["USER"] )
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

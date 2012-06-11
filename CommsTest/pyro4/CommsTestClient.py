#!/usr/bin/env python

# See CommsTest/README

import os, sys
import Pyro4

if len(sys.argv) != 3:
    print "USAGE: CommsTestClient.py HOST PORT"
    sys.exit(1)

Pyro4.config.HMAC_KEY = "cylc"

host = sys.argv[1]
port = sys.argv[2]

try:
    proxy = Pyro4.Proxy("PYRO:report@" + host + ":" + port)
except Pyro4.errors.ProtocolError, x:
    raise SystemExit( 'ForURI URI ERROR, ' + host + ': ' + str(x) )
except Exception, x:
    raise SystemExit( 'ERROR: ' + str(x) )

try:
    print proxy.get_report( os.environ["USER"] )
except Pyro4.errors.ProtocolError, x:
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

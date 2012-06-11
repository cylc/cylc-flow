#!/usr/bin/env python

# See CommsTest/README

import sys
import socket
import Pyro4

if len(sys.argv) != 1:
    print "USAGE: CommsTestServer.py"
    sys.exit(1)

Pyro4.config.HMAC_KEY = "cylc"

my_host = socket.getfqdn()

class Report(object):
    def get_report(self, name):
        return "***Hello " + name + ", this is the CommsTest server on " + my_host + "***"

port_min = 7766
port_max = 7866

daemon = Pyro4.Daemon()
uri = daemon.register( Report(), "report" )
print "[CommsTest Server listening on", daemon.locationStr + "]"
daemon.requestLoop()

#!/usr/bin/env python

import sys
import socket
import Pyro.core

if len(sys.argv) != 1:
    print "USAGE: CommsTestServer.py"
    print "(no options or arguments)"
    sys.exit(1)

my_host = socket.getfqdn()

class Report(Pyro.core.ObjBase):
    def get_report(self, name):
        return "***Hello " + name + ", this is the CommsTest server on " + my_host + "***"

daemon=Pyro.core.Daemon()
uri=daemon.connect( Report(),"report")
print "[CommsTest Server listening on", my_host + ":" + str(daemon.port) + "]"
daemon.requestLoop()

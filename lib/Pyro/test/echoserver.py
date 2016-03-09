#############################################################################
#
#	Pyro Echo Server, for test purposes
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import sys
import time
from threading import Thread
import Pyro.core
import Pyro.naming
import Pyro.errors

class EchoServer(Pyro.core.ObjBase):
    verbose=False
    def echo(self, args):
        if self.verbose:
            print ("%s - echo: %s" % (time.asctime(), args))
        return args
    def error(self):
        if self.verbose:
            print ("%s - error: generating exception" % time.asctime())
        return 1//0   # division by zero error


class NameServer(Thread):
	def __init__(self, hostname):
		Thread.__init__(self)
		self.setDaemon(1)
		self.starter = Pyro.naming.NameServerStarter()
		self.hostname=hostname
	def run(self):
		self.starter.start(hostname=self.hostname, dontlookupother=True)
	def waitUntilStarted(self):
		return self.starter.waitUntilStarted()
	def getHostAndPort(self):
	    d=self.starter.daemon
	    return d.hostname, d.port
	def shutdown(self):
	    self.starter.shutdown()
    
def startNameServer(host):
    ns=NameServer(host)
    ns.start()
    ns.waitUntilStarted()
    return ns

def main(args):
    from optparse import OptionParser
    parser=OptionParser()
    parser.add_option("-H","--host", default="localhost", help="hostname to bind server on (default=localhost)")
    parser.add_option("-p","--port", type="int", default=0, help="port to bind server on")
    parser.add_option("-n","--naming", action="store_true", default=False, help="register with nameserver")
    parser.add_option("-N","--nameserver", action="store_true", default=False, help="also start a nameserver")
    parser.add_option("-v","--verbose", action="store_true", default=False, help="verbose output")
    options,args = parser.parse_args(args)

    nameserver=None
    if options.nameserver:
        options.naming=True
        nameserver=startNameServer(options.host)
        print("")

    print ("Starting Pyro's built-in test echo server.")
    d=Pyro.core.Daemon(host=options.host, port=options.port, norange=True)
    echo=EchoServer()
    echo.verbose=options.verbose
    objectName=":Pyro.test.echoserver"
    if options.naming:
        host,port=None,None
        if nameserver is not None:
            host,port=nameserver.getHostAndPort()
        ns=Pyro.naming.NameServerLocator().getNS(host,port)
        try:
            ns.createGroup(":Pyro.test")
        except Pyro.errors.NamingError:
            pass
        d.useNameServer(ns)
        if options.verbose:
            print ("using name server at %s" % ns.URI)
    else:
        if options.verbose:
            print ("not using a name server.")
    uri=d.connect(echo, objectName)
    print ("object name = %s" % objectName)
    print ("echo uri = %s" % uri)
    print ("echo uri = PYROLOC://%s:%d/%s" % (d.hostname, d.port, objectName))
    print ("echoserver running.")
    try:
        d.requestLoop()
    finally:
        d.shutdown(disconnect=True)
        if nameserver is not None:
            #nameserver.shutdown()
            pass

if __name__=="__main__":
    main(sys.argv[1:])

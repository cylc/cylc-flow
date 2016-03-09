#############################################################################
#  
#	Event Service client base classes
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import Pyro.core, Pyro.naming, Pyro.constants
import Pyro.EventService.Server
from Pyro.EventService.Event import Event
from Pyro.errors import *

# SUBSCRIBER: subscribes to certain events.
class Subscriber(Pyro.core.CallbackObjBase):
	def __init__(self, ident=None, esURI=None):
		Pyro.core.CallbackObjBase.__init__(self)
		Pyro.core.initServer()
		Pyro.core.initClient()
		daemon = Pyro.core.Daemon()
		if esURI:
			check=Pyro.core.PyroURI(esURI)
			self.ES_uri=esURI
		else:		
			locator = Pyro.naming.NameServerLocator(identification=ident)
			self.NS = locator.getNS(host=Pyro.config.PYRO_NS_HOSTNAME)
			daemon.useNameServer(self.NS)
			self.ES_uri = self.NS.resolve(Pyro.constants.EVENTSERVER_NAME)
		daemon.connect(self)  #  will also set self.daemon...
		self.ES_ident=ident
		self.abortListen=0
		self.daemon=daemon	# make sure daemon doesn't get garbage collected now

	def getES(self):
		# we get a fresh proxy to the ES because of threading issues.
		# (proxies can not be reused across multiple threads)
		eventservice=Pyro.core.getProxyForURI(self.ES_uri)
		eventservice._setIdentification(self.ES_ident)
		return eventservice

	def subscribe(self,subjects):
		# Subscribe to one or more subjects.
		# It is safe to call this multiple times.
		self.getES().subscribe(subjects, self.getProxy())
	def subscribeMatch(self,subjectPatterns):
		# Subscribe to one or more subjects (by pattern)
		# It is safe to call this multiple times.
		self.getES().subscribeMatch(subjectPatterns, self.getProxy())
	def unsubscribe(self, subjects):
		# Unsubscribe the subscriber for the given subject(s).
		self.getES().unsubscribe(subjects, self.getProxy())

	def abort(self):
		self.abortListen=1

	def setThreading(self, threaded):
		self.getDaemon().threaded=threaded

	def listen(self):
		self.getDaemon().requestLoop(lambda s=self: not s.abortListen)

	def event(self, event):					# callback, override this!
		print event

# PUBLISHER: publishes events.
class Publisher(object):
	def __init__(self, ident=None, esURI=None):
		Pyro.core.initClient()
		if esURI:
			check=Pyro.core.PyroURI(esURI)
			self.ES_uri=esURI
		else:
			locator = Pyro.naming.NameServerLocator(identification=ident)
			ns = locator.getNS(host=Pyro.config.PYRO_NS_HOSTNAME)
			self.ES_uri = ns.resolve(Pyro.constants.EVENTSERVER_NAME)
			ns._release()   # be very sure to release the socket
		self.ES_ident = ident

	def getES(self):
		# we get a fresh proxy to the ES because of threading issues.
		# (proxies can not be reused across multiple threads)
		eventservice=Pyro.core.getProxyForURI(self.ES_uri)
		eventservice._setIdentification(self.ES_ident)
		return eventservice

	def publish(self, subjects, msg):
		es=self.getES()
		es.publish(subjects,msg)
		es._release()   # be very sure to release the socket


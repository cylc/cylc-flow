#############################################################################
#  
#	Event Service daemon and server classes
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import time, types, re, sys, traceback, os
import Pyro.core, Pyro.naming, Pyro.util, Pyro.constants
from Pyro.errors import *
from Pyro.EventService.Event import Event
import Queue
from threading import Thread

Log=Pyro.util.Log

# SUBSCRIBER - each subscriber has one of these worker threads
class Subscriber(Thread):
	def __init__(self, remote):
		Thread.__init__(self)
		self.remote=remote
		# set the callback method to ONEWAY mode:
		self.remote._setOneway("event")
		self.queue=Queue.Queue(Pyro.config.PYRO_ES_QUEUESIZE)
	def run(self):
		while 1:
			event=self.queue.get()
			if isinstance(event,Event):
				try:
					self.remote.event(event)
				except ProtocolError,x:
					break
			else:
				break # it was no Event, so exit
		# this reads all pending items from the queue so that any
		# tasks that are blocked on the queue can continue.
		(queue, self.queue) = (self.queue, None)
		try:
			while 1:
				queue.get(block=0)
		except Queue.Empty:
			pass
		# release the remote connection
		self.remote._release()
		del self.remote
	def send(self, event):
		if self.queue:
			self.queue.put(event, block=Pyro.config.PYRO_ES_BLOCKQUEUE)
	def running(self):
		return self.queue

# The EVENTSERVICE is the actual Pyro server.
#
# BTW: Subscribers are remembered trough their proxy class.
# This class is capable of being a correct key in a dictionary.
class EventService(Pyro.core.ObjBase):
	def __init__(self):
		Pyro.core.ObjBase.__init__(self)
		self.subscribers={}			# subject -> { threadname-> subscriberthread }
		self.subscribersMatch={}	# subjectPattern -> { threadname->subscriberthread }
		self.subscriptionWorkers={}	# subscriber -> subscription thread object
	def _mksequence(self, seq):
		if not (type(seq) in (types.TupleType,types.ListType)):
			return (seq,)
		return seq
	def getSubscriptionWorker(self, subscriber):
		# If this subscriber doesn't have its own subscription thread, create one.
		if subscriber not in self.subscriptionWorkers:
			worker = Subscriber(subscriber)
			worker.start()
			self.subscriptionWorkers[subscriber]=worker
			return worker
		else:
			return self.subscriptionWorkers[subscriber]
	def subscribe(self, subjects, subscriber):
		if not subjects: return
		# Subscribe into a dictionary; this way; somebody can subscribe
		# only once to this subject. Subjects are exact strings.
		for subject in self._mksequence(subjects):
			worker=self.getSubscriptionWorker(subscriber)
			self.subscribers.setdefault(subject.lower(),{}) [worker.getName()]=worker
	def subscribeMatch(self, subjects, subscriber):
		if not subjects: return
		# Subscribe into a dictionary; this way; somebody can subscribe
		# only once to this subject. Subjects are regex patterns.
		for subject in self._mksequence(subjects):
			worker=self.getSubscriptionWorker(subscriber)
			matcher = re.compile(subject,re.IGNORECASE)
			self.subscribersMatch.setdefault(matcher,{}) [worker.getName()]=worker
	def unsubscribe(self, subjects, subscriber):
		if not subjects: return
		for subject in self._mksequence(subjects):
			try:
				blaat=self.subscribers[subject.lower()]  # check for subject
				worker=self.subscriptionWorkers[subscriber]
				del self.subscribers[subject.lower()] [worker.getName()]
				self.killWorkerIfLastSubject(subscriber, worker)
			except KeyError,x:
				try:
					m=re.compile(subject,re.IGNORECASE)
					worker=self.subscriptionWorkers[subscriber]
					del self.subscribersMatch[m] [worker.getName()]
					self.killWorkerIfLastSubject(subscriber,worker)
				except KeyError,x:
					pass

	def publish(self, subjects, message):
		if not subjects: return
		# keep the creation time, this must be the same for all events.
		creationTime=time.time()
		# publish a message. Subjects must be exact strings
		for subject in self._mksequence(subjects):
			event = Event(subject, message, creationTime)
			subjectLC=subject.lower()
			try:
				for (name,s) in self.subscribers[subjectLC].items():
					try:
						if s.running():
							s.send(event)  
						else:
							try:
								del self.subscribers[subjectLC][name]
							except KeyError:
								pass
					except Queue.Full:
						pass
			except KeyError:
				pass
			# process the subject patterns
			for (m,subs) in self.subscribersMatch.items():
				if m.match(subject):
					# send event to all subscribers
					for (name,s) in subs.items():	
						try:
							if s.running():
								s.send(event)  
							else:
								try:
									del subs[name]
								except KeyError:
									pass
						except Queue.Full:
							pass

	def killWorkerIfLastSubject(self, subscriber, worker):
		item=(worker.getName(),worker)
		for v in self.subscribers.values():
			if item in v.items():
				return
		for v in self.subscribersMatch.values():
			if item in v.items():
				return
		worker.send("QUIT")
		del self.subscriptionWorkers[subscriber]


class EventServiceStarter(object):
	def __init__(self, identification=None):
		Pyro.core.initServer()
		self.running=1
		self.identification=identification
		self.started = Pyro.util.getEventObject()
	def start(self, *args, **kwargs):			# see _start for allowed arguments
		kwargs["startloop"]=1
		self._start(*args, **kwargs )
	def initialize(self, *args, **kwargs):		# see _start for allowed arguments
		kwargs["startloop"]=0
		self._start( *args, **kwargs )
	def getServerSockets(self):
		return self.daemon.getServerSockets()
	def waitUntilStarted(self,timeout=None):
		self.started.wait(timeout)
		return self.started.isSet()
	def _start(self,hostname='',port=None,startloop=1,useNameServer=1,norange=0):
		daemon = Pyro.core.Daemon(host=hostname,port=port,norange=norange)
		if self.identification:
			daemon.setAllowedIdentifications([self.identification])
			print 'Requiring connection authentication.'

		if useNameServer:
			locator = Pyro.naming.NameServerLocator(identification=self.identification)
			ns = locator.getNS()
	
			# check if ES already running
			try:
				ns.resolve(Pyro.constants.EVENTSERVER_NAME)
				print 'The Event Server appears to be already running.'
				print 'You cannot start multiple Event Servers.'
				ans=raw_input('Start new Event Server anyway (y/n)? ')
				if ans!='y':
					return
				ns.unregister(Pyro.constants.EVENTSERVER_NAME)
			except NamingError:
				pass
	
			daemon.useNameServer(ns)

		es = EventService()

		esURI=daemon.connect(es, Pyro.constants.EVENTSERVER_NAME)
		print 'URI=',esURI

		message = daemon.validateHostnameAndIP()
		if message:
			print "\nWARNING:",message,"\n"

		print 'Event Server started.'

		self.started.set()		# signal that we've started.

		if startloop:
			Log.msg('ES daemon','This is the Pyro Event Server.')
			
			try:
				if os.name!="java":
					# I use a timeout here otherwise you can't break gracefully on Windows
					daemon.setTimeout(20)
				daemon.requestLoop(lambda s=self: s.running)
			except KeyboardInterrupt:
				Log.warn('ES daemon','shutdown on user break signal')
				print 'Shutting down on user break signal.'
				self.shutdown(es)
			except:
				try:
					(exc_type, exc_value, exc_trb) = sys.exc_info()
					out = ''.join(traceback.format_exception(exc_type, exc_value, exc_trb)[-5:])
					Log.error('ES daemon', 'Unexpected exception, type',exc_type,
						'\n--- partial traceback of this exception follows:\n',
						out,'\n--- end of traceback')
					print '*** Exception occured!!! Partial traceback:'
					print out
					print '*** Resuming operations...'
				finally:	
					del exc_type, exc_value, exc_trb    # delete refs to allow proper GC

			Log.msg('ES daemon','Shut down gracefully.')
			print 'Event Server gracefully stopped.'
		else:
			# no loop, store the required objects for getServerSockets()
			self.daemon=daemon
			self.es=es
			if os.name!="java":
				daemon.setTimeout(20)  # XXX fixed timeout

	def mustContinueRunning(self):
		return self.running
	def handleRequests(self, timeout=None):
		# this method must be called from a custom event loop
		self.daemon.handleRequests(timeout=timeout)
	def shutdown(self,es):
		if es:
			# internal shutdown call with specified ES object
			daemon=es.getDaemon()
		else:
			# custom shutdown call w/o specified ES object, use stored instance
			daemon=self.daemon
			es=self.es
			del self.es, self.daemon
		try:
			daemon.disconnect(es) # clean up nicely
		except NamingError,x:
			Log.warn('ES daemon','disconnect error during shutdown:',x)
		except ConnectionClosedError,x:
			Log.warn('ES daemon','lost connection with Name Server, cannot unregister')
		self.running=0
		daemon.shutdown()


def start(argv):
	Args = Pyro.util.ArgParser()
	Args.parse(argv,'hNn:p:i:')
	if Args.hasOpt('h'):
		print 'Usage: pyro-es [-h] [-n hostname] [-p port] [-N] [-i identification]'
		print '  where -p = ES server port (0 for auto)'
		print '        -n = non-default hostname to bind on'
		print '        -N = do not use the name server'
		print '        -i = the required authentication ID for ES clients,'
		print '             also used to connect to other Pyro services'
		print '        -h = print this help'
		raise SystemExit
	hostname = Args.getOpt('n',None)
	port = Args.getOpt('p',None)
	useNameServer = not Args.hasOpt('N')
	ident = Args.getOpt('i',None)
	if port:
		port=int(port)
	norange=(port==0)
	Args.printIgnored()
	if Args.args:
		print 'Ignored arguments:',' '.join(Args.args)

	print '*** Pyro Event Server ***'
	starter=EventServiceStarter(identification=ident)
	starter.start(hostname,port,useNameServer=useNameServer,norange=norange)


# allow easy starting of the ES by using python -m
if __name__=="__main__":
	start(sys.argv[1:])

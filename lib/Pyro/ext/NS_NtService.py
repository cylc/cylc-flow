#############################################################################
#
#	An NT service that runs the Pyro Name Server
#   Author: Syver Enstad  syver-en@online.no
#
#	This is part of "Pyro" - Python Remote Objects
#	Which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import win32serviceutil
import threading
import win32service
import win32api
from BasicNTService import BasicNTService, getRegistryParameters


def setConfig():
	Pyro.config.PYRO_TRACELEVEL=3
	Pyro.config.PYRO_STORAGE = os.path.splitdrive(win32api.GetSystemDirectory())[0]+os.sep
	Pyro.config.PYRO_LOGFILE = "Pyro_NS_svc.log"
	Pyro.config.PYRO_NS_URIFILE = os.path.join(Pyro.config.PYRO_STORAGE, "Pyro_NS_URI.txt")

import os,sys
import Pyro.util
setConfig()
Log=Pyro.util.Log
import Pyro.core
import Pyro.constants
import Pyro.naming
from Pyro.naming import NameServer, PersistentNameServer, BroadcastServer, bcRequestHandler

BcServerObject = None

def startServer(hstn='', nsport=0, bcport=0, keep=0, persistent=0, dbdir=None, Guards=(None,None)):
	global BcServerObject
	if not nsport:
		nsport=Pyro.config.PYRO_NS_PORT
	if not bcport:
		bcport=Pyro.config.PYRO_NS_BC_PORT
	Pyro.core.initServer()
	PyroDaemon = Pyro.core.Daemon(host=hstn, port=nsport,norange=1)
	if Guards[0]:
		PyroDaemon.setNewConnectionValidator(Guards[0])
	if persistent:
		ns=PersistentNameServer(dbdir)
		PyroDaemon.useNameServer(ns)
		NS_URI=PyroDaemon.connectPersistent(ns,Pyro.constants.NAMESERVER_NAME)
	else:
		ns=NameServer()
		PyroDaemon.useNameServer(ns)
		NS_URI=PyroDaemon.connect(ns,Pyro.constants.NAMESERVER_NAME)
	
	BcServerObject = BroadcastServer((hstn or '',bcport),bcRequestHandler)
	if Guards[1]:
		BcServerObject.setRequestValidator(Guards[1])
	BcServerObject.keepRunning(keep)
	if keep:
		Log.msg("NS", 'Will ignore shutdown requests.')
		ns.ignoreShutdown=True
	else:
		Log.msg("NS", 'Will accept shutdown requests.')
		ns.ignoreShutdown=False

	if Guards[0] or Guards[1]:
		print 'Using security plugins:'
		if Guards[0]:
			print '  NS new conn validator =',Guards[0].__class__.__name__,'from', Guards[0].__class__.__module__
		else: print '  default NS new conn validator'
		if Guards[1]:
			print '  BC request validator  =',Guards[1].__class__.__name__,'from', Guards[1].__class__.__module__
		else: print '  default BC request validator'

	ns.publishURI(NS_URI)
	BcServerObject.setNS_URI(NS_URI)
	Log.msg('NS daemon','This is the Pyro Name Server.')
	if persistent:
		Log.msg('NS daemon','Persistent mode, database is in',ns.getDBDir())
		print 'Persistent mode, database is in',ns.getDBDir()
	Log.msg('NS daemon','Starting on',PyroDaemon.hostname,'port', PyroDaemon.port, ' broadcast server on port',bcport)

	# I use a timeout here otherwise you can't break gracefully on Windoze
	while not BcServerObject.shutdown:
		try:
			PyroDaemon.handleRequests(BcServerObject.preferredTimeOut,[BcServerObject],BcServerObject.bcCallback)
		except KeyboardInterrupt:
			Log.warn('NS daemon','shutdown on user break signal')
			BcServerObject.shutdown=1
		except:
			import traceback
			(exc_type, exc_value, exc_trb) = sys.exc_info()
			out = ''.join(traceback.format_exception(exc_type, exc_value, exc_trb)[-5:])
			Log.error('NS daemon', 'Unexpected exception, type',exc_type,
				'\n--- partial traceback of this exception follows:\n',
				out,'\n--- end of traceback')

	Log.msg('NS daemon','Shut down gracefully.')


class PyroNSThread(threading.Thread):
	""" The Pyro Naming Service will run in this thread
	"""
	def __init__(self, args, stopcallback):
		threading.Thread.__init__(self)
		Log.msg("PyroNSsvc", "initializing")
		self._args = list(args)
		Log.msg("PyroNSsvc", "args are:",self._args)
		self._stopcallback = stopcallback
		
	def run(self):
		self.startPyroNS()
		self._stopcallback()

	def startPyroNS(self):
		try:
			""" ripped out of Pyro.naming and slightly changed to
			accomodate not using sys.argv, but self._args instead
			"""
			Args = Pyro.util.ArgParser()
			Args.parse(self._args,'hkn:p:b:d:s:')
			try:
				Args.getOpt('h')
				Log.error("PyroNS_svc","""
Usage: ns [-h] [-n hostname] [-p port] [-b port]
		[-d [databasefile]] [-s securitymodule]
  where -p = NS server port
		-b = NS broadcast port
		-n = non-default server hostname
		-d = use persistent database, provide optional storage directory
		-s = use given python module with security code
		-h = print this help
""")
				raise SystemExit
			except KeyError:
				pass
			host = Args.getOpt('n','')
			port = int(Args.getOpt('p',Pyro.config.PYRO_NS_PORT))
			bcport = int(Args.getOpt('b',Pyro.config.PYRO_NS_BC_PORT))
			try:
				dbdir = Args.getOpt('d')
				persistent = 1
			except KeyError:
				persistent = 0
				dbdir = None

			# we're running as a service, always ignore remote shutdown requests
			keep=1

			try:
				secmod = __import__(Args.getOpt('s'),locals(),globals())
				Guards = (secmod.NSGuard(), secmod.BCGuard())
			except ImportError,x:
				Log.msg("NS", 'Error loading security module:',x)
				raise SystemExit
			except KeyError:
				secmod = None
				Guards = (None,None)

			if Args.ignored:
				Log.warn("PyroNS_svc",'Ignored options:',Args.ignored)
			if Args.args:
				Log.warn("PyroNS_svc",'Ignored arguments:',Args.args)

			Log.msg("PyroNS_svc","Starting the Name Server.")
			startServer(host,port,bcport,keep,persistent,dbdir,Guards)
		except Exception,x :
			Log.error("NS daemon","COULD NOT START!!!",x)
			raise SystemExit

	
class PyroNS_NTService(BasicNTService):
	_svc_name_ = 'PyroNS'
	_svc_display_name_ = "Pyro Naming Service"
	_svc_description_ = 'Provides name resolution services for Pyro objects'
	def __init__(self, args):
		super(PyroNS_NTService, self).__init__(args)
		setConfig()
		try:
			args = getRegistryParameters(self._svc_name_).split()
		except Exception,x:
			Log.error("PyroNS_svc","PROBLEM GETTING ARGS FROM REGISTRY:",x)
		self._nsThread = PyroNSThread(args, self.SvcStop)
		
	def _doRun(self):
		""" Overriden """
		self._nsThread.start()

	def _doStop(self):
		""" Overridden """
		global BcServerObject
		BcServerObject.shutdown = 1
		self._nsThread.join()

	def SvcStop(self):
		"""Overriden """
		super(PyroNS_NTService, self).SvcStop()
		

if __name__ == '__main__':
	PyroNS_NTService.HandleCommandLine()

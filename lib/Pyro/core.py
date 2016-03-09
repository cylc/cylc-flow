#############################################################################
#  
#	Pyro Core Library
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

from __future__ import with_statement
import sys, time, re, os, weakref
import imp, marshal, new, socket
from pickle import PicklingError
import Pyro.constants, Pyro.util, Pyro.protocol, Pyro.errors
from Pyro.errors import *
from types import UnboundMethodType, MethodType, BuiltinMethodType, TupleType, StringType, UnicodeType
if Pyro.util.supports_multithreading():
	import threading

Log=Pyro.util.Log


def _checkInit(pyrotype="client"):
	if not getattr(Pyro.config, Pyro.constants.CFGITEM_PYRO_INITIALIZED):
		# If Pyro has not been initialized explicitly, do it automatically.
		if pyrotype=="server":
			initServer()
		else:
			initClient()


#############################################################################
#
#	ObjBase		- Server-side object implementation base class
#	              or master class with the actual object as delegate
#
#	SynchronizedObjBase - Just the same, but with synchronized method
#                         calls (thread-safe).
#
#############################################################################

class ObjBase(object):
	def __init__(self):
		self.objectGUID=Pyro.util.getGUID()
		self.delegate=None
		self.lastUsed=time.time()		# for later reaping unused objects
		if Pyro.config.PYRO_MOBILE_CODE:
			self.codeValidator=lambda n,m,a: 1  # always accept
	def GUID(self):
		return self.objectGUID
	def setGUID(self, guid):			# used with persistent name server
		self.objectGUID = guid
	def delegateTo(self,delegate):
		self.delegate=delegate
	def setPyroDaemon(self, daemon):
		# This will usually introduce a cyclic reference between the
		# object and the daemon. Use a weak ref if available.
		# NOTE: if you correctly clean up the object (that is, disconnect it from the daemon)
		# the cyclic reference is cleared correctly, and no problem occurs.
		# NOTE: you have to make sure your original daemon object doesn't get garbage collected
		# if you still want to use the objects! You have to keep a ref. to the daemon somewhere.
		if daemon:
			self.daemon=weakref.proxy(daemon)
		else:
			self.daemon=None
	def setCodeValidator(self, v):
		if not callable(v):
			raise TypeError("codevalidator must be a callable object")
		self.codeValidator=v
	def getDaemon(self):
		return self.daemon
	def getLocalStorage(self):
		return self.daemon.getLocalStorage()
	def _gotReaped(self):
		# Called when daemon reaps this object due to unaccessed time
		# Override this method if needed; to act on this event
		pass
	def getProxy(self):
		return self.daemon.getProxyForObj(self)
	def getAttrProxy(self):
		return self.daemon.getAttrProxyForObj(self)
	def Pyro_dyncall(self, method, flags, args):
		# update the timestamp
		self.lastUsed=time.time()
		# find the method in this object, and call it with the supplied args.
		keywords={}
		if flags & Pyro.constants.RIF_Keywords:
			# reconstruct the varargs from a tuple like
			#  (a,b,(va1,va2,va3...),{kw1:?,...})
			keywords=args[-1]
			args=args[:-1]
		if flags & Pyro.constants.RIF_Varargs:
			# reconstruct the varargs from a tuple like (a,b,(va1,va2,va3...))
			args=args[:-1]+args[-1]
		if keywords and type(keywords.iterkeys().next()) is unicode and sys.platform!="cli":
			# IronPython sends all strings as unicode, but apply() doesn't grok unicode keywords.
			# So we need to rebuild the keywords dict with str keys... 
			keywords = dict([(str(k),v) for k,v in keywords.iteritems()])
		# If the method is part of ObjBase, never call the delegate object because
		# that object doesn't implement that method. If you don't check this,
		# remote attributes won't work with delegates for instance, because the
		# delegate object doesn't implement _r_xa. (remote_xxxattr)
		if method in dir(ObjBase):
			return getattr(self,method) (*args,**keywords)
		else:
			# try..except to deal with obsoleted string exceptions (raise "blahblah")
			try :
				return getattr(self.delegate or self,method) (*args,**keywords)
			except :
				exc_info = sys.exc_info()
				try:
					if type(exc_info[0]) == StringType :
						if exc_info[1] == None :
							raise Exception, exc_info[0], exc_info[2]
						else :
							raise Exception, "%s: %s" % (exc_info[0], exc_info[1]), exc_info[2]
					else :
						raise
				finally:
					del exc_info   # delete frame to allow proper GC

	# remote getattr/setattr support:
	def _r_ha(self, attr):
		try:
			attr = getattr(self.delegate or self,attr)
			if type(attr) in (UnboundMethodType, MethodType, BuiltinMethodType):
				return 1 # method
		except:
			pass
		return 2 # attribute
	def _r_ga(self, attr):
		return getattr(self.delegate or self, attr)
	def _r_sa(self, attr, value):
		setattr(self.delegate or self, attr, value)
	# remote code downloading support (server downloads from client):
	def remote_supply_code(self, name, module, sourceaddr):
		# XXX this is nasty code, and also duplicated in protocol.py _retrieveCode()
		if Pyro.config.PYRO_MOBILE_CODE and self.codeValidator(name,module,sourceaddr):
			try:
				imp.acquire_lock()   # threadsafe imports
				if name in sys.modules and getattr(sys.modules[name],'_PYRO_bytecode',None):
					# already have this module, don't import again
					# we checked for the _PYRO_bytecode attribute because that is only
					# present when all loading code below completed successfully
					return
				Log.msg('ObjBase','loading supplied code: ',name,'from',str(sourceaddr))
				if module[0:4]!=imp.get_magic():
					# compile source code
					code=compile(module,'<downloaded>','exec')
				else:
					# read bytecode from the client
					code=marshal.loads(module[8:])

				# make the module hierarchy and add all names to sys.modules
				name=name.split('.')
				path=''
				mod=new.module("pyro-agent-context")
				for m in name:
					path+='.'+m
					# use already loaded modules instead of overwriting them
					real_path = path[1:]
					if sys.modules.has_key(real_path):
						mod = sys.modules[real_path]
					else:
						setattr(mod,m,new.module(path[1:]))
						mod=getattr(mod,m)
						sys.modules[path[1:]]=mod
				# execute the module code in the right module.
				exec code in mod.__dict__
				# store the bytecode for possible later reference if we need to pass it on
				mod.__dict__['_PYRO_bytecode'] = module
			finally:
				imp.release_lock()
		else:
			Log.warn('ObjBase','attempt to supply code denied: ',name,'from',str(sourceaddr))
			raise PyroError('attempt to supply code denied')

	# remote code retrieve support (client retrieves from server):
	def remote_retrieve_code(self, name):
		# XXX codeValidator: can we somehow get the client's address it is sent to?
		# XXX this code is ugly. And duplicated in protocol.py remoteInvocation.
		if Pyro.config.PYRO_MOBILE_CODE and self.codeValidator(name,None,None):
			Log.msg("ObjBase","supplying code: ",name)
			try:
				importmodule=new.module("pyro-server-import")
				try:
					exec "import " + name in importmodule.__dict__
				except ImportError:
					Log.error("ObjBase","Client wanted a non-existing module:", name)
					raise PyroError("Client wanted a non-existing module", name)
				m=eval("importmodule."+name)
				# try to load the module's compiled source, or the real .py source if that fails.
				# note that the source code (.py) is opened with universal newline mode
				(filebase,ext)=os.path.splitext(m.__file__)
				if ext.startswith(".PY"):
					exts = ( (".PYO","rb"), (".PYC","rb"), (".PY","rU") )	# uppercase
				else:
					exts = ( (".pyo","rb"), (".pyc","rb"), (".py","rU") )	# lowercase
				for ext,mode in exts:
					try:
						m=open(filebase+ext, mode).read()
						return m  # supply the module to the client!
					except:
						pass
				Log.error("ObjBase","cannot read module source code for module:", name)
				raise PyroError("cannot read module source code")
			finally:
				del importmodule
		else:
			Log.error("ObjBase","attempt to retrieve code denied:", name)
			raise PyroError("attempt to retrieve code denied")


class SynchronizedObjBase(ObjBase):
    def __init__(self):
        ObjBase.__init__(self)
        self.synlock=Pyro.util.getLockObject()
    def Pyro_dyncall(self, method, flags, args):
        with self.synlock:
            return ObjBase.Pyro_dyncall(self, method,flags,args)


# Use this class instead if you're using callback objects and you
# want to see local exceptions. (otherwise they go back to the calling server...)
class CallbackObjBase(ObjBase):
	def __init__(self):
		ObjBase.__init__(self)
	def Pyro_dyncall(self, method, flags, args):
		try:
			return ObjBase.Pyro_dyncall(self,method,flags,args)
		except Exception,x:
			# catch all errors
			Log.warn('CallbackObjBase','Exception in callback object: ',x)
			raise PyroExceptionCapsule(x,str(x))


#############################################################################
#
#	PyroURI		- Pyro Universal Resource Identifier
#
#	This class represents a Pyro URI (which consists of four parts,
#	a protocol identifier, an IP address, a portnumber, and an object ID.
#	
#	The URI can be converted to a string representation (str converter).
#	The URI can also be read back from such a string (reinitFromString).
#	The URI can be initialised from its parts (init).
#	The URI can be initialised from a string directly, if the init
#	 code detects a ':' and '/' in the host argument (which is then
#        assumed to be a string URI, not a host name/ IP address).
#
#############################################################################

class PyroURI(object):
	def __init__(self,host,objectID=0,port=0,prtcol='PYRO'):
		# if the 'host' arg is a PyroURI, copy contents
		if isinstance(host, PyroURI):
			self.init(host.address, host.objectID, host.port, host.protocol)
		else:
			# If the 'host' arg contains '://', assume it's an URI string.
			if host.find('://')>0:
				self.reinitFromString(host)
			else:
				if not objectID:
					raise URIError('invalid URI format')
				self.init(host, objectID, port, prtcol)
	def __str__(self):
		return self.protocol+'://'+self.address+':'+str(self.port)+'/'+self.objectID
	def __repr__(self):
		return '<PyroURI \''+str(self)+'\'>'
	def __hash__(self):
		# XXX this is handy but not safe. If the URI changes, the object will be in the wrong hash bucket.
		return hash(str(self))
	def __cmp__(self, o):
		return cmp(str(self), str(o))
	def clone(self):
		return PyroURI(self)
	def init(self,host,objectID,port=0,prtcol='PYRO'):
		if '/' in host:
			raise URIError('malformed hostname')
		if Pyro.config.PYRO_DNS_URI:
			self.address = host
		else:
			self.address=Pyro.protocol.getIPAddress(host)
			if not self.address:
				raise URIError('unknown host')
		if port:
			if type(port)==type(1):
				self.port=port
			else:
				raise TypeError("port must be integer")
		else:
			self.port=Pyro.config.PYRO_PORT
		self.protocol=prtcol
		self.objectID=objectID
	def reinitFromString(self,arg):
		if arg.startswith('PYROLOC') or arg.startswith('PYRONAME'):
			uri=processStringURI(arg)
			self.init(uri.address,uri.objectID,uri.port,uri.protocol)
			return
		x=re.match(r'(?P<protocol>[^\s:/]+)://(?P<hostname>[^\s:]+):?(?P<port>\d+)?/(?P<id>\S*)',arg)
		if x:
			port=None
			if x.group('port'):
				port=int(x.group('port'))
			self.init(x.group('hostname'), x.group('id'), port, x.group('protocol'))
			return
		Log.error('PyroURI','invalid URI format passed: '+arg)
		raise URIError('invalid URI format')
	def getProxy(self):
		return DynamicProxy(self)
	def getAttrProxy(self):
		return DynamicProxyWithAttrs(self)


#
#	This method takes a string representation of a Pyro URI
#	and parses it. If it's a meta-protocol URI such as
#	PYRONAME://.... it will do what is needed to make
#	a regular PYRO:// URI out of it (resolve names etc).
#
def processStringURI(URI):
	# PYRONAME(SSL)://[hostname[:port]/]objectname
	x=re.match(r'(?P<protocol>PYRONAME|PYRONAMESSL)://(((?P<hostname>[^\s:]+):(?P<port>\d+)/)|((?P<onlyhostname>[^\s:]+)/))?(?P<name>\S*)',URI)
	if x:
		protocol=x.group('protocol')
		if protocol=="PYRONAMESSL":
			raise ProtocolError("NOT SUPPORTED YET: "+protocol) # XXX obviously, this should be implemented
		hostname=x.group('hostname') or x.group('onlyhostname')
		port=x.group('port')
		name=x.group('name')
		import Pyro.naming
		loc=Pyro.naming.NameServerLocator()
		if port:
			port=int(port)
		NS=loc.getNS(host=hostname,port=port)
		return NS.resolve(name)
	# PYROLOC(SSL)://hostname[:port]/objectname
	x=re.match(r'(?P<protocol>PYROLOC|PYROLOCSSL)://(?P<hostname>[^\s:]+):?(?P<port>\d+)?/(?P<name>\S*)',URI)
	if x:
		protocol=x.group('protocol')
		hostname=x.group('hostname')
		port=x.group('port')
		if port:
			port=int(port)
		else:
			port=0
		name=x.group('name')
		return PyroURI(hostname,name,port,protocol)
	if URI.startswith('PYROLOC') or URI.startswith('PYRONAME'):
		# hmm should have matched above. Likely invalid.
		raise URIError('invalid URI format')
	# It's not a meta-protocol such as PYROLOC or PYRONAME,
	# let the normal Pyro URI deal with it.
	# (it can deal with regular PYRO: and PYROSSL: protocols)
	return PyroURI(URI)


#############################################################################
#
#	DynamicProxy	- dynamic Pyro proxy
#
#	Can be used by clients to invoke objects for which they have no
#	precompiled proxy.
#
#############################################################################

def getProxyForURI(URI):
	return DynamicProxy(URI)
def getAttrProxyForURI(URI):
	return DynamicProxyWithAttrs(URI)

class _RemoteMethod(object):
	# method call abstraction, adapted from Python's xmlrpclib
	# it would be rather easy to add nested method calls, but
	# that is not compatible with the way that Pyro's method
	# calls are defined to work ( no nested calls ) 
	def __init__(self, send, name):
		self.__send = send
		self.__name = name
	def __call__(self, *args, **kwargs):
		return self.__send(self.__name, args, kwargs)

class DynamicProxy(object):
	def __init__(self, URI):
		_checkInit() # init required
		if type(URI) in (StringType,UnicodeType):
			URI=processStringURI(URI)
		self.URI = URI
		self.objectID = URI.objectID
		# Delay adapter binding to enable transporting of proxies.
		# We just create an adapter, and don't connect it...
		self.adapter = Pyro.protocol.getProtocolAdapter(self.URI.protocol)
		# ---- don't forget to register local vars with DynamicProxyWithAttrs, see below
	def __del__(self):
		try:
			self.adapter.release(nolog=1)
		except (AttributeError, RuntimeError):
			pass
	def _setIdentification(self, ident):
		self.adapter.setIdentification(ident)
	def _setNewConnectionValidator(self, validator):
		self.adapter.setNewConnectionValidator(validator)
	def _setOneway(self, methods):
		if type(methods) not in (type([]), type((0,))):
			methods=(methods,)
		self.adapter.setOneway(methods)
	def _setTimeout(self,timeout):
		self.adapter.setTimeout(timeout)
	def _transferThread(self, newOwnerThread=None):
		pass # dummy function to retain API compatibility with Pyro 3.7
	def _release(self):
		if self.adapter:
			self.adapter.release()
	def _local(self):
		return self.URI._local()
	def _islocal(self):
		return self.URI._islocal()
	def __copy__(self):			# create copy of current proxy object
		proxyCopy = DynamicProxy(self.URI)
		proxyCopy.adapter.setIdentification(self.adapter.getIdentification(), munge=False)   # copy identification info
		proxyCopy._setTimeout(self.adapter.timeout)
		proxyCopy._setOneway(self.adapter.onewayMethods)
		proxyCopy._setNewConnectionValidator(self.adapter.getNewConnectionValidator())
		return proxyCopy
	def __deepcopy__(self, arg):
		raise PyroError("cannot deepcopy a proxy")
	def __getattr__(self, name):
		if name in ("__getnewargs__","__getinitargs__"):		# allows it to be safely pickled
			raise AttributeError()
		return _RemoteMethod(self._invokePYRO, name)
	def __repr__(self):
		return "<"+self.__class__.__name__+" for "+str(self.URI)+">"
	def __str__(self):
		return repr(self)
	def __hash__(self):
		# makes it possible to use this class as a key in a dict
		return hash(self.objectID)
	def __eq__(self,other):
		# makes it possible to compare two proxies using objectID
		return hasattr(other,"objectID") and self.objectID==other.objectID
	def __ne__(self,other):
		# makes it possible to compare two proxies using objectID
		return not hasattr(other,"objectID") or self.objectID!=other.objectID
	def __nonzero__(self):
		return 1
	def __coerce__(self,other):
		# makes it possible to compare two proxies using objectID (cmp)
		if hasattr(other,"objectID"):
			return (self.objectID, other.objectID)
		return None

	def _invokePYRO(self, name, vargs, kargs):
		if not self.adapter.connected():
			# rebind here, don't do it from inside the remoteInvocation because deadlock will occur
			self.adapter.bindToURI(self.URI)
		return self.adapter.remoteInvocation(name, Pyro.constants.RIF_VarargsAndKeywords, vargs, kargs)

	# Pickling support, otherwise pickle uses __getattr__:
	def __getstate__(self):
		# for pickling, return a non-connected copy of ourselves:
		cpy = self.__copy__()
		cpy._release()
		return cpy.__dict__
	def __setstate__(self, args):
		# for pickling, to restore the pickled state
		self.__dict__.update(args)

	
class DynamicProxyWithAttrs(DynamicProxy):
	_local_attrs = ("_local_attrs","URI", "objectID", "adapter", "_attr_cache")
	def __init__(self, URI):
		self._attr_cache = {}
		DynamicProxy.__init__(self, URI)
	def _r_ga(self, attr, value=0):
		if value:
			return _RemoteMethod(self._invokePYRO, "_r_ga") (attr)  # getattr
		else:
			return _RemoteMethod(self._invokePYRO, "_r_ha") (attr)  # hasattr
	def findattr(self, attr):
		if attr in self._attr_cache.keys():
			return self._attr_cache[attr]
		# look it up and cache the value
		self._attr_cache[attr] = self._r_ga(attr)
		return self._attr_cache[attr]
	def __copy__(self):		# create copy of current proxy object
		return DynamicProxyWithAttrs(self.URI)
	def __setattr__(self, attr, value):
		if attr in self._local_attrs:
			self.__dict__[attr]=value
		else:
			result = self.findattr(attr)
			if result==2: # attribute
				return _RemoteMethod(self._invokePYRO, "_r_sa") (attr,value)
			else:
				raise AttributeError('not an attribute')
	def __getattr__(self, attr):
		# allows it to be safely pickled
		if attr not in ("__getnewargs__","__getinitargs__", "__hash__","__eq__","__ne__") and attr not in self._local_attrs:
			result=self.findattr(attr)
			if result==1: # method
				return _RemoteMethod(self._invokePYRO, attr)
			elif result:
				return self._r_ga(attr, 1)
		raise AttributeError
		

#############################################################################
#
#	Daemon		- server-side Pyro daemon
#
#	Accepts and dispatches incoming Pyro method calls.
#
#############################################################################

# The pyro object that represents the daemon.
# The daemon is not directly remotely accessible, for security reasons.
class DaemonServant(ObjBase):
	def __init__(self, daemon):
		ObjBase.__init__(self)
		self.daemon=weakref.proxy(daemon)
	def getRegistered(self):
		return self.daemon.getRegistered()
	def ResolvePYROLOC(self, name):
		return self.daemon.ResolvePYROLOC(name)
		
# The daemon itself:
class Daemon(Pyro.protocol.TCPServer, ObjBase):
	def __init__(self,prtcol='PYRO',host=None,port=0,norange=0,publishhost=None):
		ObjBase.__init__(self)
		self.NameServer = None
		self.connections=[]
		_checkInit("server") # init required
		self.setGUID(Pyro.constants.INTERNAL_DAEMON_GUID)
		self.implementations={Pyro.constants.INTERNAL_DAEMON_GUID:(DaemonServant(self),'__PYRO_Internal_Daemon')}
		self.persistentConnectedObjs=[] # guids
		self.transientsCleanupAge=0
		self.transientsMutex=Pyro.util.getLockObject()
		self.nscallMutex=Pyro.util.getLockObject()
		if host is None:
			host=Pyro.config.PYRO_HOST
		if publishhost is None:
			publishhost=Pyro.config.PYRO_PUBLISHHOST

		# Determine range scanning or random port allocation
		if norange:
			# Fixed or random port allocation
			# If port is zero, OS will randomly assign, otherwise,
			# attempt to use the provided port value
			self.port = port
			portrange = 1
		else:
			# Scanning port allocation
			if port:
				self.port = port
			else:
				self.port = Pyro.config.PYRO_PORT
			portrange=Pyro.config.PYRO_PORT_RANGE

		if not publishhost:
			publishhost=host
		errormsg=''
		for i in range(portrange):
			try:
				Pyro.protocol.TCPServer.__init__(self, self.port, host, Pyro.config.PYRO_MULTITHREADED,prtcol)
				if not self.port:
					# If we bound to an OS provided port, report it
					self.port = self.sock.getsockname()[1]
				self.hostname = publishhost or Pyro.protocol.getHostname()
				self.protocol = prtcol
				self.adapter = Pyro.protocol.getProtocolAdapter(prtcol)
				self.validateHostnameAndIP()  # ignore any result message... it's in the log already.
				return
			except ProtocolError,msg:
				errormsg=msg
				self.port+=1
		Log.error('Daemon','Couldn\'t start Pyro daemon: ' +str(errormsg))
		raise DaemonError('Couldn\'t start Pyro daemon: ' +str(errormsg))
	
	# to be called to stop all connections and shut down.
	def shutdown(self, disconnect=False):
		Pyro.protocol.TCPServer.shutdown(self)
		if disconnect:
			self.__disconnectObjects()
	def __disconnectObjects(self):
		# server shutting down, unregister all known objects in the NS
		if self.NameServer and Pyro and Pyro.constants:
			with self.nscallMutex:
				if Pyro.constants.INTERNAL_DAEMON_GUID in self.implementations:
					del self.implementations[Pyro.constants.INTERNAL_DAEMON_GUID]
				if self.implementations:
					Log.warn('Daemon','Shutting down but there are still',len(self.implementations),'objects connected - disconnecting them')
				for guid in self.implementations.keys():
					if guid not in self.persistentConnectedObjs:
						(obj,name)=self.implementations[guid]
						if name:
							try:
								self.NameServer.unregister(name)
							except Exception,x:
								Log.warn('Daemon','Error while unregistering object during shutdown:',x)
				self.implementations={}

	def __del__(self):
		self.__disconnectObjects() # unregister objects
		try:
			del self.adapter
			Pyro.protocol.TCPServer.__del__(self)
		except (AttributeError, RuntimeError):
			pass

	def __str__(self):
		return '<Pyro Daemon on '+self.hostname+':'+str(self.port)+'>'
	def __getstate__(self):
		raise PicklingError('no access to the daemon')

	def validateHostnameAndIP(self):
		# Checks if hostname is sensible. Returns None if it is, otherwise a message
		# telling what's wrong if it isn't too serious. If things are really bad,
		# expect an exception to be raised. Things are logged too.
		if not self.hostname:
			Log.error("Daemon","no hostname known")
			raise socket.error("no hostname known for daemon")
		if self.hostname!="localhost":
			ip = Pyro.protocol.getIPAddress(self.hostname)
			if ip is None:
				Log.error("Daemon","no IP address known")
				raise socket.error("no IP address known for daemon")
			if not ip.startswith("127.0."):
				return None  # this is good!
		# 127.0.x.x or 'localhost' is a warning situation!
		msg="daemon bound on hostname that resolves to loopback address 127.0.x.x"
		Log.warn("Daemon",msg)
		Log.warn("Daemon","hostname="+self.hostname)
		return msg
	
	def useNameServer(self,NS):
		self.NameServer=NS
	def getNameServer(self):
		return self.NameServer
	def setTimeout(self, timeout):
		self.adapter.setTimeout(timeout)
	def setAllowedIdentifications(self, ids):
		self.getNewConnectionValidator().setAllowedIdentifications(ids)
	def setTransientsCleanupAge(self, secs):
		self.transientsCleanupAge=secs
		if self.threaded:
			Log.msg('Daemon','creating Grim Reaper thread for transients, timeout=',secs)
			reaper=threading.Thread(target=self._grimReaper)
			reaper.setDaemon(1)   # thread must exit at program termination.
			reaper.start()
	def _grimReaper(self):
		# this runs in a thread.
		while self.transientsCleanupAge>0:
			time.sleep(self.transientsCleanupAge/5)
			self.reapUnusedTransients()

	def getProxyForObj(self, obj):
		return DynamicProxy( PyroURI(self.hostname,
				obj.GUID(), prtcol=self.protocol, port=self.port) )
	def getAttrProxyForObj(self, obj):
		return DynamicProxyWithAttrs( PyroURI(self.hostname,
				obj.GUID(), prtcol=self.protocol, port=self.port) )

	def connectPersistent(self, obj, name=None):
		# when a persistent entry is found in the NS, that URI is
		# used instead of the supplied one, if the address matches.
		if name and self.NameServer:
			with self.nscallMutex:
				try:
					newURI = PyroURI(self.hostname, obj.GUID(), prtcol=self.protocol, port=self.port)
					URI=self.NameServer.resolve(name)
					if (URI.protocol,URI.address,URI.port)==(newURI.protocol,newURI.address,newURI.port):
						# reuse the previous object ID
						obj.setGUID(URI.objectID)
						# enter the (object,name) in the known impl. dictionary
						self.implementations[obj.GUID()]=(obj,name)
						self.persistentConnectedObjs.append(obj.GUID())
						obj.setPyroDaemon(self)
						return URI
					else:
						# name exists, but address etc. is wrong. Remove it.
						# then continue so it wil be re-registered.
						try: self.NameServer.unregister(name)
						except NamingError: pass
				except NamingError:
					pass
		# Register normally.		
		self.persistentConnectedObjs.append(obj.GUID())
		return self.connect(obj, name)

	def connect(self, obj, name=None):
		URI = PyroURI(self.hostname, obj.GUID(), prtcol=self.protocol, port=self.port)
		# if not transient, register the object with the NS
		if name:
			with self.nscallMutex:
				if self.NameServer:
					self.NameServer.register(name, URI)
				else:
					Log.warn('Daemon','connecting object without name server specified:',name)
		# enter the (object,name) in the known implementations dictionary
		self.implementations[obj.GUID()]=(obj,name)
		obj.setPyroDaemon(self)
		return URI

	def disconnect(self,obj):		# obj can be either the object that was registered, or its uid
		try:
			if isinstance(obj,Pyro.core.ObjBase):
				obj_uid=obj.GUID()
			else:
				obj_uid=str(obj)
			if obj_uid==Pyro.constants.INTERNAL_DAEMON_GUID:
				return   # never allow to remove ourselves from the registry
			if self.NameServer and self.implementations[obj_uid][1]:
				with self.nscallMutex:
					# only unregister with NS if it had a name (was not transient)
					self.NameServer.unregister(self.implementations[obj_uid][1])
			del self.implementations[obj_uid]
			if obj_uid in self.persistentConnectedObjs:
				self.persistentConnectedObjs.remove(obj_uid)
			# XXX Clean up connections/threads to this object?
			#     Can't be done because thread/socket is not associated with single object 
		finally:
			if isinstance(obj,Pyro.core.ObjBase):
				obj.setPyroDaemon(None)

	def getRegistered(self):
		r={}
		for guid in self.implementations.keys():
			r[guid]=self.implementations[guid][1]	# keep only the names
		return r

	def handleInvocation(self, conn):	# overridden from TCPServer
		# called in both single- and multithreaded mode
		self.getLocalStorage().caller=conn
		self.getAdapter().handleInvocation(self, conn)
		self.reapUnusedTransients()

	def reapUnusedTransients(self):
		if not self.transientsCleanupAge: return
		now=time.time()
		with self.transientsMutex:
			for (obj,name) in self.implementations.values()[:]:   # use copy of list
				if not name:
					# object is transient, reap it if timeout requires so.
					if (now-obj.lastUsed)>self.transientsCleanupAge:
						self.disconnect(obj)
						obj._gotReaped()

	def handleError(self,conn,onewaycall=False):			# overridden from TCPServer
		try:
			(exc_type, exc_value, exc_trb) = sys.exc_info()
			if exc_type==ProtocolError:
				# Problem with the communication protocol, shut down the connection
				# XXX is shutting down what we want???
				Log.error('Daemon','protocol error occured:',exc_value)
				Log.error('Daemon','Due to network error: shutting down connection with',conn)
				self.removeConnection(conn)
			else:
				exclist = Pyro.util.formatTraceback(exc_type, exc_value, exc_trb)
				out =''.join(exclist)
				Log.warn('Daemon', 'Exception during processing of request from',
					conn,' type',exc_type,
					'\n--- traceback of this exception follows:\n',
					out,'\n--- end of traceback')
				if exc_type==PyroExceptionCapsule:
					sys.stdout.flush()
					# This is a capsuled exception, used with callback objects.
					# That means we are actually the daemon on the client.
					# Return the error to the other side and raise exception locally once more.
					# (with a normal exception, it is not raised locally again!)
					# only send the exception object if it's not a oneway call.
					if not onewaycall:
						self.adapter.returnException(conn,exc_value.excObj,0,exclist) # don't shutdown
					exc_value.raiseEx()
				else:
					# normal exception, only return exception object if it's not a oneway call
					if not onewaycall:
						self.adapter.returnException(conn,exc_value,0,exclist) # don't shutdown connection

		finally:
			# clean up circular references to traceback info to allow proper GC
			del exc_type, exc_value, exc_trb

	def getAdapter(self):
		# overridden from TCPServer
		return self.adapter

	def getLocalObject(self, guid):
		# return a local object registered with the given guid
		return self.implementations[guid][0]
	def getLocalObjectForProxy(self, proxy):
		# return a local object registered with the guid to which the given proxy points
		return self.implementations[proxy.objectID][0]

	def ResolvePYROLOC(self, name):
		# this gets called from the protocol adapter when
		# it wants the daemon to resolve a local object name (PYROLOC: protocol)
		Log.msg('Daemon','resolving PYROLOC name: ',name)
		for o in self.implementations.keys():
			if self.implementations[o][1]==name:
				return o
		raise NamingError('no object found by this name',name)


#############################################################################
#
#	Client/Server Init code
#
#############################################################################

# Has init been performed already?
_init_server_done=0
_init_client_done=0
_init_generic_done=0

def _initGeneric_pre():
	global _init_generic_done
	if _init_generic_done:
		return
	if Pyro.config.PYRO_TRACELEVEL == 0: return
	try:
		out='\n'+'-'*60+' NEW SESSION\n'+time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))+ \
			'   Pyro Initializing, version '+Pyro.constants.VERSION+'\n'
		Log.raw(out)
	except IOError,e:
		sys.stderr.write('PYRO: Can\'t write the tracefile '+Pyro.config.PYRO_LOGFILE+'\n'+str(e))

def _initGeneric_post():
	global _init_generic_done
	setattr(Pyro.config, Pyro.constants.CFGITEM_PYRO_INITIALIZED,1)
	if Pyro.config.PYRO_TRACELEVEL == 0: return
	try:
		if not _init_generic_done:
			out='Configuration settings are as follows:\n'
			for item in dir(Pyro.config):
				if item[0:4] =='PYRO':
					out+=item+' = '+str(Pyro.config.__dict__[item])+'\n'
			Log.raw(out)
		Log.raw('Init done.\n'+'-'*70+'\n')
	except IOError:
		pass
	_init_generic_done=1	


def initClient(banner=0):
	global _init_client_done
	if _init_client_done: return
	_initGeneric_pre()
	if Pyro.config.PYRO_TRACELEVEL >0: Log.raw('This is initClient.\n')
	Pyro.config.finalizeConfig_Client()
	_initGeneric_post()
	if banner:
		print 'Pyro Client Initialized. Using Pyro V'+Pyro.constants.VERSION
	_init_client_done=1
	
def initServer(banner=0, storageCheck=1):
	global _init_server_done
	if _init_server_done: return
	_initGeneric_pre()
	if Pyro.config.PYRO_TRACELEVEL >0: Log.raw('This is initServer.\n')
	Pyro.config.finalizeConfig_Server(storageCheck=storageCheck)
	_initGeneric_post()
	if banner:
		print 'Pyro Server Initialized. Using Pyro V'+Pyro.constants.VERSION
	_init_server_done=1


if __name__=="__main__":
	print "Pyro version:",Pyro.constants.VERSION

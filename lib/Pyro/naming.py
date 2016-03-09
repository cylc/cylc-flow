#############################################################################
#
#	Pyro Name Server
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

from __future__ import with_statement
import sys, os, socket, time, traceback, errno
import dircache, shutil, SocketServer
import Pyro.constants, Pyro.core, Pyro.errors, Pyro.protocol, Pyro.util
if Pyro.util.supports_multithreading():
	import threading

NS_SYSCMD_LOCATION='location'
NS_SYSCMD_SHUTDOWN='shutdown'

Log = Pyro.util.Log

#############################################################################
#
# The Pyro NameServer Locator.
# Use a broadcast mechanism to find the broadcast server of the NS which
# can provide us with the URI of the NS.
# Can also perform direct lookup (no broadcast) if the host is specified.
# (in that case, the 'port' argument is the Pyro port, not a broadcast port).
#
#############################################################################

class NameServerLocator(object):
	def __init__(self, identification=None):
		Pyro.core._checkInit()	# init required
		self.identification=identification

	def sendSysCommand(self,request,host=None,port=None,trace=0,logerrors=1,bcaddr=None):
		try:
			# Try the 'first' name server.
			# Note that if no host is specified, a broadcast is used,
			# and that one is sent to both name servers in parallel.
			return self.__sendSysCommand(request, host, port, trace, logerrors, Pyro.constants.NSROLE_PRIMARY, bcaddr)
		except KeyboardInterrupt:
			raise
		except (socket.error, Pyro.errors.PyroError):
			if not port:
				# the 'first' name server failed, try the second
				try:
					result=self.__sendSysCommand(request, host, port, trace, logerrors, Pyro.constants.NSROLE_SECONDARY, bcaddr)
					# found the second!
					# switch config for first and second so that the second one (which we found) will now be tried first
					Pyro.config.PYRO_NS2_HOSTNAME, Pyro.config.PYRO_NS_HOSTNAME = Pyro.config.PYRO_NS_HOSTNAME, Pyro.config.PYRO_NS2_HOSTNAME
					Pyro.config.PYRO_NS2_PORT, Pyro.config.PYRO_NS_PORT = Pyro.config.PYRO_NS_PORT, Pyro.config.PYRO_NS2_PORT
					Pyro.config.PYRO_NS2_BC_PORT, Pyro.config.PYRO_NS_BC_PORT = Pyro.config.PYRO_NS_BC_PORT, Pyro.config.PYRO_NS2_BC_PORT
					Pyro.config.PYRO_NS2_BC_ADDR, Pyro.config.PYRO_NS_BC_ADDR = Pyro.config.PYRO_NS_BC_ADDR, Pyro.config.PYRO_NS2_BC_ADDR
					return result
				except (socket.error, Pyro.errors.PyroError):
					# Could not find using broadcast. Try the current host and localhost as well.
					# But only if there's no explicit host parameter given.
					if host:
						raise Pyro.errors.NamingError("could not find NameServer on host "+host)
					else:
						for host in (Pyro.protocol.getHostname(), "localhost"):
							if trace:
								print "Trying host",host
							Log.msg('NameServerLocator','Trying host',host)
							try:
								result=self.__sendSysCommand(request, host, port, trace, logerrors, Pyro.constants.NSROLE_PRIMARY)
								Pyro.config.PYRO_NS_HOSTNAME = host
								return result
							except Pyro.errors.ConnectionDeniedError:
							    raise
							except (socket.error, Pyro.errors.PyroError),x:
								pass
						else:
							raise Pyro.errors.NamingError("could not find NameServer")
			else:
				raise

	def __sendSysCommand(self,request,host=None,port=None,trace=0,logerrors=1,role=Pyro.constants.NSROLE_PRIMARY,bcaddr=None):
		HPB={Pyro.constants.NSROLE_PRIMARY: (Pyro.config.PYRO_NS_HOSTNAME, Pyro.config.PYRO_NS_PORT, Pyro.config.PYRO_NS_BC_PORT, Pyro.config.PYRO_NS_BC_ADDR),
		     Pyro.constants.NSROLE_SECONDARY: (Pyro.config.PYRO_NS2_HOSTNAME, Pyro.config.PYRO_NS2_PORT, Pyro.config.PYRO_NS2_BC_PORT, Pyro.config.PYRO_NS2_BC_ADDR) }
		if not host:
			host=HPB[role][0]
		if port:
			port1=port2=port
		else:
			if not host:
				# select the default broadcast ports
				port1 = HPB[Pyro.constants.NSROLE_PRIMARY][2]
				port2 = HPB[Pyro.constants.NSROLE_SECONDARY][2]
			else:
				# select the default port (normal)
				port = HPB[role][1]
		# We must discover the location of the name server.
		# Pyro's NS can answer to broadcast requests.
		try:
			if host:
				# use direct lookup with PYROLOC: mechanism, no broadcast
				if trace:
					print 'Locator: contacting Pyro Name Server...'
				uri=Pyro.core.PyroURI(host,Pyro.constants.NAMESERVER_NAME,port,'PYROLOC')
				prox=Pyro.core.getProxyForURI(uri)
				prox._setIdentification(self.identification)
				if request==NS_SYSCMD_LOCATION:
					prox.ping()	# force resolving of PYROLOC: uri
					return prox.URI # return resolved uri
				elif request==NS_SYSCMD_SHUTDOWN:
					return prox._shutdown()
				else:
					raise ValueError("invalid command specified")

			# No host specified. Use broadcast mechanism
			if os.name=='java' and sys.version_info<(2,5):
				# jythons older than 2.5 don't have working broadcast
				msg="Skipping UDP broadcast (older jythons don't support this operation)"
				if trace:
					print msg
				raise Pyro.errors.PyroError(msg)
			if bcaddr:
				try:
					socket.gethostbyname(bcaddr)
				except socket.error:
					msg="invalid broadcast address '%s'" % bcaddr
					if trace:
						print msg
					raise ValueError(msg)
				destination1 = (bcaddr, port1)
				destination2 = (bcaddr, port2)
			else:
				destination1 = (Pyro.config.PYRO_NS_BC_ADDR or '<broadcast>', port1)
				destination2 = (Pyro.config.PYRO_NS2_BC_ADDR or '<broadcast>', port2)
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			if hasattr(socket,'SO_BROADCAST'):
				s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
			
			if trace:
				print 'Locator: searching Pyro Name Server...'
			try:
				bc_retries=Pyro.config.PYRO_BC_RETRIES
				if bc_retries<0:
					bc_retries=sys.maxint-1
				bc_retries = min(sys.maxint-1, bc_retries)
				for i in xrange(bc_retries+1):
					# send request to both Pyro NS (if running in paired mode)
					s.sendto(request, destination1)
					if destination2!=destination1:
						s.sendto(request, destination2)
					timeout=min(sys.maxint,Pyro.config.PYRO_BC_TIMEOUT)
					if timeout<0:
						timeout=None
					ins,outs,exs = Pyro.protocol.safe_select([s],[],[s],timeout)
					if s in ins:
						# return the info of the first NS that responded.
						reply, fromaddr = s.recvfrom(1000)
						return reply
					if trace and i<Pyro.config.PYRO_BC_RETRIES:
						print 'Locator: retry',i+1
			finally:
				s.close()
		except socket.error,e:
			if logerrors:
				Log.error('NameServerLocator','network error:',e)
			if trace:
				print 'Locator: network error:',e
			raise
		if logerrors:
			Log.error('NameServerLocator','Name Server not responding to broadcast')
		raise Pyro.errors.PyroError('Name Server not responding')
	
	def detectNS(self,host=None,port=None,trace=0,bcaddr=None):
		# just try to detect an existing NS. Don't log errors
		return Pyro.core.PyroURI(self.sendSysCommand(NS_SYSCMD_LOCATION,host,port,trace,0,bcaddr))

	def getNS(self,host=None,port=None,trace=0,bcaddr=None):
		reply = self.sendSysCommand(NS_SYSCMD_LOCATION,host,port,trace,1,bcaddr)
		Log.msg('NameServerLocator','Name Server found:',reply)
		ns=NameServerProxy(Pyro.core.PyroURI(reply),self.identification)
		ns._setIdentification(self.identification)
		return ns
		

# NOTE: The NameServerProxy class below is hand crafted.
# This is because we want to enforce the default group name on all name
# arguments that are not absolute.
# In doing so, we make sure that each object name is passed as an
# absolute name (from the name space root) too. This is needed because
# the NS has no state and can only process absolute names for each request.
# Also, the PYRO_NS_DEFAULTGROUP configitem is used to expand non-absolute
# names to absolute names. Because this is done in the proxy, each
# client can have its own PYRO_NS_DEFAULTGROUP.

class NameServerProxy(object):
	def __init__(self,URI,identification=None,noconnect=0):
		self.URI = URI
		self.objectID = URI.objectID
		self.adapter = Pyro.protocol.getProtocolAdapter(self.URI.protocol)
		self.adapter.setIdentification(identification)
		if noconnect:
			self.adapter.URI=URI
		else:
			self.adapter.bindToURI(URI)
		self.adapter.setOneway(["_synccall"])
	def _release(self):
		if self.adapter:
			self.adapter.release()
			
	def __remoteinvoc(self, *args):
		try:
			if not self.adapter.connected():
				# rebind here, don't do it from inside the remoteInvocation because deadlock will occur
				self.adapter.bindToURI(self.URI)
			return self.adapter.remoteInvocation(*args)
		except Pyro.errors.ProtocolError,x:
			# The remote invocation failed. Try to find the NS again.
			Log.warn('NameServerProxy','Name Server communication problem:',x,' URI was:',self.URI)
			Log.msg('NameServerProxy','trying to find NS again...')
			self.URI=NameServerLocator().detectNS()
			self.objectID=self.URI.objectID
			self.adapter.bindToURI(self.URI)
			Log.msg('NameServerProxy','found NS at',self.URI,".... retry call")
			return self.adapter.remoteInvocation(*args)
			
	def ping(self):
		return self.__remoteinvoc('ping',0)
	def resync(self):
		return self.__remoteinvoc('resync',0)
	def register(self,name,URI):
		return self.__remoteinvoc('register',0,_expandName(name),URI)
	def resolve(self,name):
		return self.__remoteinvoc('resolve',0,_expandName(name))
	def flatlist(self):
		return self.__remoteinvoc('flatlist',0)
	def unregister(self,name):
		return self.__remoteinvoc('unregister',0,_expandName(name))
	def createGroup(self,gname):
		return self.__remoteinvoc('createGroup',0,_expandName(gname))
	def deleteGroup(self,gname):
		return self.__remoteinvoc('deleteGroup',0,_expandName(gname))
	def list(self,gname):
		return self.__remoteinvoc('list',0,_expandName(gname))
	def setMeta(self, name, meta):
		return self.__remoteinvoc('setMeta',0,_expandName(name),meta)
	def getMeta(self, name):
		return self.__remoteinvoc('getMeta',0,_expandName(name))
	def fullName(self,name):
		return _expandName(name)
	def _shutdown(self):
		return self.__remoteinvoc('_shutdown',0)
	def _setSystemMeta(self, name, meta):
		return self.__remoteinvoc('_setSystemMeta',0,_expandName(name),meta)
	def _getSystemMeta(self, name):
		return self.__remoteinvoc('_getSystemMeta',0,_expandName(name))
	def _setIdentification(self, ident):
		self.adapter.setIdentification(ident)
	def _resync(self, twinProxy):
		return self.adapter.remoteInvocation('_resync',0,twinProxy)
	def _synccall(self, *args):
		self.adapter.remoteInvocation('_synccall',Pyro.constants.RIF_Varargs, args)
	def _transferThread(self, newOwnerThread=None):
		pass # dummy function to retain API compatibility with Pyro 3.7
	def __copy__(self):
		# return a Non-connected copy of ourselves)
		proxyCopy = NameServerProxy(self.URI, noconnect=1)
		proxyCopy.adapter.setIdentification(self.adapter.getIdentification(), munge=False)   # copy identification info
		return proxyCopy
	def __deepcopy__(self, arg):
		raise Pyro.errors.PyroError("cannot deepcopy a nameserver proxy")
	def __getstate__(self):
		# for pickling, return a non-connected copy of ourselves:
		copy = self.__copy__()
		copy._release()
		return copy.__dict__
	def __setstate__(self, args):
		# this appears to be necessary otherwise pickle won't work
		self.__dict__=args
				

# Can be used to expand names to absolute names (NS proxy uses this)
# but user code should use the fullName method of the proxy.
def _expandName(name):
	if Pyro.config.PYRO_NS_DEFAULTGROUP[0]!=':':
		raise Pyro.errors.NamingError('default group name is not absolute')
	if name:
		if name[0]==':':
			return name
		return Pyro.config.PYRO_NS_DEFAULTGROUP+'.'+name
	else:
		return Pyro.config.PYRO_NS_DEFAULTGROUP


#############################################################################
#
#	The Name Server (a Pyro Object).
#
#	It has more methods than the ones available in the proxy (above)
#	but that is because the other methods are private and for internal
#	use only.
#
#############################################################################


class NameServer(Pyro.core.ObjBase):
	def __init__(self, role=Pyro.constants.NSROLE_SINGLE, identification=None):
		Pyro.core.ObjBase.__init__(self)
		self.root=NamedTree('<root>')
		self.lock=Pyro.util.getLockObject()
		self.role=role
		self.otherNS=None
		self.ignoreShutdown=False
		if role in (Pyro.constants.NSROLE_PRIMARY, Pyro.constants.NSROLE_SECONDARY):
			# for paired mode with identification, we need to remember the ident string
			adapter=Pyro.protocol.getProtocolAdapter("PYRO")
			adapter.setIdentification(identification)
			self.identification=adapter.getIdentification() # grab the munged ident
		# create default groups
		self.createGroup(':'+'Pyro')
		self.createGroup(Pyro.config.PYRO_NS_DEFAULTGROUP)
		Log.msg("NameServer","Running in",
		 {Pyro.constants.NSROLE_SINGLE:"single",
		  Pyro.constants.NSROLE_PRIMARY:"primary",
		  Pyro.constants.NSROLE_SECONDARY:"secondary"}[self.role],"mode" )
			
	def _initialResyncWithTwin(self, twinProxy):
		if twinProxy:
			try:
				Log.msg("NameServer","Initial resync with other NS at",twinProxy.URI.address,"port",twinProxy.URI.port)
				print "Initial Resync with other NS at",twinProxy.URI.address,"port",twinProxy.URI.port
				# keep old NS (self) registration
				oldNSreg=self.resolve(Pyro.constants.NAMESERVER_NAME)
				proxyForMe=NameServerProxy(self.getProxy().URI,noconnect=1)
				proxyForMe.adapter.setIdentification(self.identification,munge=False) # set pre-munged ident
				self.root=twinProxy._resync(proxyForMe)
				# reset self registration
				try:
					self.unregister(Pyro.constants.NAMESERVER_NAME)
				except:
					pass
				self.register(Pyro.constants.NAMESERVER_NAME,oldNSreg)
				self.otherNS=twinProxy
				Log.msg("NameServer","database sync complete.")
				print "Database synchronized."
			except Pyro.errors.NamingError,x:
				print x
				raise
			
	def _removeTwinNS(self):
		self.otherNS=None
			
	def register(self,name,URI):
		(origname,name)=name,self.validateName(name)
		URI=self.validateURI(URI)
		with self.lock:
			(group, name)=self.locateGrpAndName(name)
			if len(name or "")<1:
				raise Pyro.errors.NamingError('invalid name',origname)
			if isinstance(group,NameValue):
				raise Pyro.errors.NamingError('parent is no group', group.name)
			try:
				group.newleaf(name,URI)
				Log.msg('NameServer','registered',name,'with URI',str(URI))
				self._dosynccall("register",origname,URI)
			except KeyError:
				Log.msg('NameServer','name already exists:',name)
				raise Pyro.errors.NamingError('name already exists',name)

	def unregister(self,name):
		(origname,name)=name,self.validateName(name)
		with self.lock:
			(group, name)=self.locateGrpAndName(name)
			if len(name or "")<1:
				raise Pyro.errors.NamingError('invalid name',origname)
			try:
				group.cutleaf(name)
				Log.msg('NameServer','unregistered',name)
				self._dosynccall("unregister",origname)
			except KeyError:
				raise Pyro.errors.NamingError('name not found',name)
			except ValueError:
				Log.msg('NameServer','attempt to remove a group:',name)
				raise Pyro.errors.NamingError('is a group, not an object',name)

	def resolve(self,name):
		# not thread-locked: higher performance and not necessary.
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			if isinstance(branch,NameValue):
				return branch.value
			else:
				Log.msg('NameServer','attempt to resolve groupname:',name)
				raise Pyro.errors.NamingError('attempt to resolve groupname',name)
		except KeyError:
			raise Pyro.errors.NamingError('name not found',name)
		except AttributeError:
			raise Pyro.errors.NamingError('group not found',name)

	def flatlist(self):
		# return a dump
		with self.lock:
			r=self.root.flatten()
		for i in xrange(len(r)):
			r[i]=(':'+r[i][0], r[i][1])
		return r

	def ping(self):
		# Just accept a remote invocation.
		# This method is used to check if NS is still running,
		# and also by the locator if a direct lookup is needed.
		pass

	# --- sync support (twin NS)
	def _resync(self, twinProxy):
		if self.role!=Pyro.constants.NSROLE_SINGLE:
			Log.msg("NameServer","resync requested from NS at",twinProxy.URI.address,"port",twinProxy.URI.port)
			print "Resync requested from NS at",twinProxy.URI.address,"port",twinProxy.URI.port
			self.otherNS=twinProxy
			with self.lock:
				return self._getSyncDump()
		else:
			Log.warn("NameServer","resync requested from",twinProxy.URI,"but not running in correct mode")
			raise Pyro.errors.NamingError("The (other) NS is not running in 'primary' or 'secondary' mode")
	
	# remotely called:
	def _synccall(self, method, *args):
		# temporarily disable the other NS
		oldOtherNS, self.otherNS = self.otherNS, None
		getattr(self, method) (*args)
		self.otherNS = oldOtherNS
		
	def resync(self):
		if self.role==Pyro.constants.NSROLE_SINGLE:
			raise Pyro.errors.NamingError("NS is not running in 'primary' or 'secondary' mode")
		if self.otherNS:
			try:
				self._initialResyncWithTwin(self.otherNS)
				return
			except Exception:
				pass
		raise Pyro.errors.NamingError("cannot resync: twin NS is unknown or unreachable")

	# local helper:
	def _dosynccall(self, method, *args):
		if self.role!=Pyro.constants.NSROLE_SINGLE and self.otherNS:
			try:
				self.otherNS._synccall(method, *args)
			except Exception,x:
				Log.warn("NameServer","ignored error in _synccall - but removing other NS",x)
				self.otherNS=None
		
	# --- hierarchical naming support
	def createGroup(self,groupname):
		groupname=self.validateName(groupname)
		if len(groupname)<2:
			raise Pyro.errors.NamingError('invalid groupname', groupname)
		with self.lock:
			(parent,name)=self.locateGrpAndName(groupname)
			if isinstance(parent,NameValue):
				raise Pyro.errors.NamingError('parent is no group', groupname)
			try:
				parent.newbranch(name)
				Log.msg('NameServer','created group',groupname)
				self._dosynccall("createGroup",groupname)
			except KeyError:
				raise Pyro.errors.NamingError('group already exists',name)

	def deleteGroup(self,groupname):
		groupname=self.validateName(groupname)
		if groupname==':':
			Log.msg('NameServer','attempt to deleteGroup root group')
			raise Pyro.errors.NamingError('not allowed to delete root group')
		with self.lock:
			(parent,name)=self.locateGrpAndName(groupname)
			try:
				parent.cutbranch(name)
				Log.msg('NameServer','deleted group',name)
				self._dosynccall("deleteGroup",groupname)
			except KeyError:
				raise Pyro.errors.NamingError('group not found',groupname)
			except ValueError:
				raise Pyro.errors.NamingError('is no group',groupname)
			
	def list(self,groupname):
		# not thread-locked: higher performance and not necessary.
		if not groupname:
			groupname=':'
		groupname=self.validateName(groupname)
		try:
			return self.getBranch(groupname).list()
		except KeyError:
			raise Pyro.errors.NamingError('group not found',groupname)
		except AttributeError:
			raise Pyro.errors.NamingError('is no group',groupname)
			
	# --- meta info support
	def setMeta(self, name, meta):
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			branch.setMeta(meta)
			self._dosynccall("setMeta",name,meta)
		except KeyError:
			raise Pyro.errors.NamingError('name not found',name)
		except AttributeError:
			raise Pyro.errors.NamingError('group not found',name)
	
	def getMeta(self, name):
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			return branch.getMeta()
		except KeyError:
			raise Pyro.errors.NamingError('name not found',name)
		except AttributeError:
			raise Pyro.errors.NamingError('group not found',name)

	def _setSystemMeta(self, name, meta):
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			branch.setSystemMeta(meta)
			self._dosynccall("_setSystemMeta",name,meta)
		except KeyError:
			raise Pyro.errors.NamingError('name not found',name)
		except AttributeError:
			raise Pyro.errors.NamingError('group not found',name)
	
	def _getSystemMeta(self, name):
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			return branch.getSystemMeta()
		except KeyError:
			raise Pyro.errors.NamingError('name not found',name)
		except AttributeError:
			raise Pyro.errors.NamingError('group not found',name)

    # --- shut down the server
	def _shutdown(self):
		if self.ignoreShutdown:
			Log.msg('NameServer','received shutdown request, but shutdown is denied')
			return 'Shutdown request denied'
		else:
			Log.msg('NameServer','received shutdown request, will shutdown shortly')
			self.getDaemon().shutdown()
			return "Will shut down shortly"
        
	# --- private methods follow
	def _getSyncDump(self):
		return self.root

	def locateGrpAndName(self,name):
		# ASSUME name is absolute (from root) (which is required here)
		idx=name.rfind('.')
		if idx>=0:
			# name is hierarchical
			grpname=name[:idx]
			name=name[idx+1:]
			try:
				return (self.getBranch(grpname), name)
			except KeyError:
				raise Pyro.errors.NamingError('(parent)group not found',grpname)
		else:
			# name is in root
			return (self.root, name[1:])

	def getBranch(self,name):
		# ASSUME name is absolute (from root) (which is required here)
		name=name[1:]
		if name:
			return reduce(lambda x,y: x[y], name.split('.'), self.root)
		else:
			return self.root

	def validateName(self,name):
		if name[0]==':':
			if ('' not in name.split('.')):
				for i in name:
					if ord(i)<33 or ord(i)>126 or i=='\\':
						raise Pyro.errors.NamingError('invalid character(s) in name',name)
				return name
			else:
				raise Pyro.errors.NamingError('invalid name',name)
		else:
			# name is not absolute. Make it absolute.
			return _expandName(name)

	def validateURI(self,URI):
		if isinstance(URI, Pyro.core.PyroURI):
			return URI
		try:
			return Pyro.core.PyroURI(URI)
		except:
			raise Pyro.errors.NamingError('invalid URI',URI)

	def publishURI(self, uri, verbose=0):
		# verbose is not used - always prints the uri.
		uri=str(uri)
		print 'URI is:',uri
		try:
			f=open(Pyro.config.PYRO_NS_URIFILE,'w')
			f.write(uri+'\n'); f.close()
			print 'URI written to:',Pyro.config.PYRO_NS_URIFILE
			Log.msg('NameServer','URI written to',Pyro.config.PYRO_NS_URIFILE)
		except:
			Log.warn('NameServer','Couldn\'t write URI to',Pyro.config.PYRO_NS_URIFILE)

#############################################################################
#
#	NamedTree data type. Used for the hierarchical name server.
#
#############################################################################

class NameSpaceSystemMeta(object):
	def __init__(self, node, timestamp, owner):
		self.timestamp=timestamp
		self.owner=owner
		if isinstance(node, NamedTree):
			self.type=0  # tree
		else:
			self.type=1  # leaf
	def __str__(self):
		return "[type="+str(self.type)+" timestamp="+str(self.timestamp)+" owner="+str(self.owner)+"]"

		
# All nodes in the namespace (groups, or namevalue pairs--leafs) have
# a shared set of properties, most notably: meta information.
class NameSpaceNode(object):
	def __init__(self, name, meta, owner):
		self.name=name
		self.systemMeta = NameSpaceSystemMeta(self, time.time(), owner)
		self.userMeta = meta
	def getMeta(self):
		return self.userMeta
	def getSystemMeta(self):
		return self.systemMeta
	def setMeta(self,meta):
		self.userMeta=meta
	def setSystemMeta(self,meta):
		if isinstance(meta, NameSpaceSystemMeta):
			self.systemMeta=meta
		else:
			raise TypeError("system meta info must be NameSpaceSystemMeta object")

class NameValue(NameSpaceNode):
	def __init__(self, name, value=None, meta=None, owner=None):
		NameSpaceNode.__init__(self, name, meta, owner)
		self.value=value

class NamedTree(NameSpaceNode):
	def __init__(self, name, meta=None, owner=None):
		NameSpaceNode.__init__(self, name, meta, owner)
		self.branches={}
	def newbranch(self,name):
		if name in self.branches.keys():
			raise KeyError,'name already exists'
		t = NamedTree(name)
		self.branches[name]=t
		return t
	def newleaf(self,name,value=None):
		if name in self.branches.keys():
			raise KeyError,'name already exists'
		l = NameValue(name,value)
		self.branches[name]=l
		return l
	def cutleaf(self,name):
		if isinstance(self.branches[name], NameValue):
			del self.branches[name]
		else:
			raise ValueError,'not a leaf'
	def cutbranch(self,name):
		if isinstance(self.branches[name], NamedTree):
			del self.branches[name]
		else:
			raise ValueError,'not a branch'
	def __getitem__(self,name):
		return self.branches[name]
	def list(self):
		l=[]
		for (k,v) in self.branches.items():
			if isinstance(v, NamedTree):
				l.append( (k,0) )	# tree
			elif isinstance(v, NameValue):
				l.append( (k,1) )	# leaf
			else:
				raise ValueError('corrupt tree')
		return l
	def flatten(self,prefix=''):
		flat=[]
		for (k,v) in self.branches.items():
			if isinstance(v, NameValue):
				flat.append( (prefix+k, v.value) )
			elif isinstance(v, NamedTree):
				flat.extend(v.flatten(prefix+k+'.'))
		return flat
				

		
#############################################################################
#
#	The Persistent Name Server (a Pyro Object).
#	This implementation uses the hierarchical file system to
#	store the groups (as directories) and objects (as files).
#
#############################################################################

_PNS_META_SUFFIX=".ns_meta"

class PersistentNameServer(NameServer):
	def __init__(self, dbdir=None, role=Pyro.constants.NSROLE_SINGLE, identification=None):
		self.dbroot=os.path.join(Pyro.config.PYRO_STORAGE,dbdir or 'Pyro_NS_database')
		self._initdb_1()
		try:
			NameServer.__init__(self, role=role, identification=identification)
		except Pyro.errors.NamingError:
			pass
		self._initdb_2()

	def _initdb_1(self):
		# root is not a NamedTree but a directory
		try:
			os.mkdir(self.dbroot)
		except OSError,x:
			if x.errno not in (errno.EEXIST, errno.EBUSY):
				raise
	def _initdb_2(self):
		# make sure that the 2 initial groups (Pyro and Default) exist
		try: self.createGroup(':'+'Pyro')
		except Pyro.errors.NamingError: pass
		try: self.createGroup(Pyro.config.PYRO_NS_DEFAULTGROUP)
		except Pyro.errors.NamingError: pass

	def getDBDir(self):
		return self.dbroot

	def _initialResyncWithTwin(self, twinProxy):
		if twinProxy:
			Log.msg("NameServer","Initial resync with other NS at",twinProxy.URI.address,"port",twinProxy.URI.port)
			# keep old NS (self) registration
			oldNSreg=self.resolve(Pyro.constants.NAMESERVER_NAME)
			proxyForMe=NameServerProxy(self.getProxy().URI,noconnect=1)
			proxyForMe.adapter.setIdentification(self.identification,munge=False) # set pre-munged ident
			syncdump=twinProxy._resync(proxyForMe)
			self.otherNS = None   # temporarily disable twin NS ref
			# clear the old database
			Log.msg("NameServer","erasing old database",self.dbroot)
			shutil.rmtree(self.dbroot)
			self._initdb_1()   # phase 2 (creation of default groups) is not needed here
			Log.msg("NameServer","store sync database")
			for group,smeta,umeta in syncdump[0]:
				try:
					if group!=':':
						dirnam = self.translate(group)
						os.mkdir(dirnam)
					if smeta:
						self._setSystemMeta(group,smeta)
					if umeta:
						self.setMeta(group,umeta)
				except EnvironmentError,x:
					Log.warn("NameServer","problem creating group",group,x)
			for name,uri,smeta,umeta in syncdump[1]:
				try:
					origname,name=name,self.validateName(name)
					fn=self.translate(name)
					open(fn,'w').write(uri+'\n')
					if smeta:
						self._setSystemMeta(name,smeta)
					if umeta:
						self.setMeta(name,umeta)
				except Pyro.errors.NamingError,x:
					Log.warn("NameServer","problem registering name",name,x)
			# reset registration of self
			try:
				self.unregister(Pyro.constants.NAMESERVER_NAME)
			except:
				pass
			self.register(Pyro.constants.NAMESERVER_NAME,oldNSreg)
			self.otherNS=twinProxy
			Log.msg("NameServer","database sync complete.")
			print "Database synchronized."

	def register(self,name,URI):
		origname,name=name,self.validateName(name)
		URI=self.validateURI(URI)
		fn=self.translate(name)
		with self.lock:
			if os.access(fn,os.R_OK):
				Log.msg('NameServer','name already exists:',name)
				raise Pyro.errors.NamingError('name already exists',name)
			try:
				open(fn,'w').write(str(URI)+'\n')
				self._dosynccall("register",origname,URI)
				Log.msg('NameServer','registered',name,'with URI',str(URI))
			except IOError,x:
				if x.errno==errno.ENOENT:
					raise Pyro.errors.NamingError('(parent)group not found')
				elif x.errno==errno.ENOTDIR:
					raise Pyro.errors.NamingError('parent is no group')
				else:
					raise Pyro.errors.NamingError(str(x))

	def unregister(self,name):
		origname,name=name,self.validateName(name)
		fn=self.translate(name)
		with self.lock:
			try:
				os.remove(fn)
				self._dosynccall("unregister",origname)
				Log.msg('NameServer','unregistered',name)
			except OSError,x:
				if x.errno==errno.ENOENT:
					raise Pyro.errors.NamingError('name not found',name)
				elif x.errno==errno.EISDIR:
					Log.msg('NameServer','attempt to remove a group:',name)
					raise Pyro.errors.NamingError('is a group, not an object',name)
				else:
					raise Pyro.errors.NamingError(str(x))
			
	def resolve(self,name):
		# not thread-locked: higher performance and not necessary.
		name=self.validateName(name)
		fn = self.translate(name)
		try:
			return Pyro.core.PyroURI(open(fn).read())
		except IOError,x:
			if x.errno==errno.ENOENT:
				raise Pyro.errors.NamingError('name not found',name)
			elif x.errno==errno.EISDIR:
				Log.msg('NameServer','attempt to resolve groupname:',name)
				raise Pyro.errors.NamingError('attempt to resolve groupname',name)
			else:
				raise Pyro.errors.NamingError(str(x))

	def flatlist(self):
		dbroot=self.translate(':')
		with self.lock:
			flat=[]
			for f in self._filelist(dbroot,dbroot):
				f=self._unescapefilename(f)
				flat.append((f, self.resolve(f)))
			return flat

	# --- hierarchical naming support
	def createGroup(self,groupname):
		groupname=self.validateName(groupname)
		dirnam = self.translate(groupname)
		with self.lock:
			try:
				os.mkdir(dirnam)
				self._dosynccall("createGroup",groupname)
				Log.msg('NameServer','created group',groupname)
			except OSError,x:
				if x.errno in (errno.EEXIST, errno.EBUSY):
					raise Pyro.errors.NamingError('group already exists',groupname)
				elif x.errno == errno.ENOENT:
					raise Pyro.errors.NamingError('(parent)group not found')
				else:
					raise Pyro.errors.NamingError(str(x))

	def deleteGroup(self,groupname):
		groupname=self.validateName(groupname)
		if groupname==':':
			Log.msg('NameServer','attempt to deleteGroup root group')
			raise Pyro.errors.NamingError('not allowed to delete root group')
		dirnam = self.translate(groupname)
		with self.lock:
			if not os.access(dirnam,os.R_OK):
				raise Pyro.errors.NamingError('group not found',groupname)
			try:
				shutil.rmtree(dirnam)
				self._dosynccall("deleteGroup",groupname)
				Log.msg('NameServer','deleted group',groupname)
			except OSError,x:
				if x.errno==errno.ENOENT:
					raise Pyro.errors.NamingError('group not found',groupname)
				elif x.errno==errno.ENOTDIR:
					raise Pyro.errors.NamingError('is no group',groupname)
				else:
					raise Pyro.errors.NamingError(str(x))
			
	def list(self,groupname):
		if not groupname:
			groupname=':'
		groupname=self.validateName(groupname)
		dirnam=self.translate(groupname)
		with self.lock:
			if os.access(dirnam,os.R_OK):
				if os.path.isfile(dirnam):
					raise Pyro.errors.NamingError('is no group',groupname)
				else:
					l = dircache.listdir(dirnam)
					entries = []
					for e in l:
						if e.endswith(_PNS_META_SUFFIX):
							continue
						else:
							objname=self._unescapefilename(e)
							if os.path.isdir(os.path.join(dirnam,e)):
								entries.append((objname,0))		# dir has code 0
							else:
								entries.append((objname,1))		# leaf has code 1
					return entries
			raise Pyro.errors.NamingError('group not found',groupname)


	# --- private methods follow
	
	def _getSyncDump(self):
		def visitor(arg,dirname,names):
			shortdirname=dirname[len(self.dbroot)+len(os.path.sep):]
			if shortdirname.endswith(_PNS_META_SUFFIX):
				return
			name = ':'+shortdirname.replace(os.path.sep,'.')
			smeta=self._getSystemMeta(name)
			umeta=self.getMeta(name)
			arg[0].append( (name, smeta,umeta) )
			for n in names:
				if n.endswith(_PNS_META_SUFFIX):
					continue
				n=os.path.join(dirname,n)
				if os.path.isfile(n):
					v=open(n,'r').read().strip()
					name=':'+(n[len(self.dbroot)+len(os.path.sep):]).replace(os.path.sep,'.')
					smeta=self._getSystemMeta(name)
					umeta=self.getMeta(name)
					arg[1].append( (name, v, smeta,umeta) )
		result=( [], [] )   # (groups, names)
		os.path.walk(self.dbroot, visitor, result)
		return result

	def _unescapefilename(self, name):
		parts=name.split('\\')
		res=[parts[0]]
		myappend=res.append
		del parts[0]
		for item in parts:
			if item[1:2]:
				try:
					myappend(chr(int(item[:2], 16)) + item[2:])
				except ValueError:
					myappend('\\' + item)
			else:
				myappend('\\' + item)
		return "".join(res)
	def _escapefilename(self,name):
		name=name.replace(os.path.sep,'\\%02x' % ord(os.path.sep)) # escape path separators in the name
		name=name.replace(':','\\%02x' % ord(':')) # also get rid of any ':' 's
		return name
		
	# recursive file listing, output is like "find <path> -type f"
	# but using NS group separator chars
	def _filelist(self,root,path):
		try:
			(filez,dirz) = Pyro.util.listdir(path)
		except OSError:
			raise Pyro.errors.NamingError('group not found')
			
		files=[]
		for f in filez:
			if f.endswith(_PNS_META_SUFFIX):
				continue
			elif path==root:
				files.append(':'+f)
			else:
				p=path[len(root):].replace(os.sep, '.')
				files.append(':'+p+'.'+f)
		for d in dirz:
			files.extend(self._filelist(root,os.path.join(path,d)))
		return files

	# Pyro NS name to filesystem path translation
	def translate(self,name):
		if name[0]==':':
			name=name[1:]
		name=self._escapefilename(name)
		args=[self.dbroot]+name.split('.')
		return os.path.join(*args)

	def getBranch(self,name):
		tr = self.translate(name)
		if os.path.exists(tr):
			return PersistentNameSpaceNode(filename=tr+_PNS_META_SUFFIX)
		else:
			raise Pyro.errors.NamingError('name not found',name)

# XXX this is a bit of a hack. Only metadata is stored here,
# and it's only used from getBranch, which in turn is only used
# from the set/get meta functions.
class PersistentNameSpaceNode(NameSpaceNode):
	def __init__(self, filename, name=None, meta=None, owner=None):
		NameSpaceNode.__init__(self, name, meta, owner)
		self.filename=filename
		if not name:
			# init from file
			try:
				(sysmeta, usermeta)=Pyro.util.getPickle().load(open(self.filename,"rb"))
				NameSpaceNode.setSystemMeta(self, sysmeta)
				NameSpaceNode.setMeta(self, usermeta)
			except Exception:
				pass # just use empty meta...
		else:
			self._writeToFile()
	def setMeta(self,meta):
		NameSpaceNode.setMeta(self, meta)
		self._writeToFile()
	def setSystemMeta(self,meta):
		NameSpaceNode.setSystemMeta(self, meta)
		self._writeToFile()
	def _writeToFile(self):
		Pyro.util.getPickle().dump( (self.getSystemMeta(), self.getMeta()) , open(self.filename,"wb"), Pyro.config.PYRO_PICKLE_FORMAT)
		

		
#############################################################################
#
# The broadcast server which listens to broadcast requests of clients who
# want to discover our location, or send other system commands.
#
#############################################################################


class BroadcastServer(SocketServer.UDPServer):

	nameServerURI = ''	# the Pyro URI of the Name Server

	def __init__(self, addr, bcRequestHandler,norange=0):
		if norange:
			portrange=1
		else:
			portrange=Pyro.config.PYRO_PORT_RANGE
		(location,port)=addr
		for port in range(port, port+portrange):
			try:
				SocketServer.UDPServer.__init__(self, (location,port), bcRequestHandler)
				return			# got it!
			except socket.error:
				continue		# try the next port in the list
		raise    # port range exhausted... re-raise the socket error.
		
	def server_activate(self):
		self.requestValidator=lambda x,y: 1  # default: accept all
		self.shutdown=0				# should the server loop stop?
		self.preferredTimeOut=3.0	# preferred timeout for the server loop
			
	def setNS_URI(self,URI):
		self.nameServerURI=str(URI)
	def setRequestValidator(self, validator):
		self.requestValidator=validator
	def keepRunning(self, keep):
		self.ignoreShutdown = keep	# ignore shutdown requests (i.e. keep running?)

	def bcCallback(self,ins):
		for i in ins:
			i.handle_request()

	def verify_request(self, req, addr):
		return self.requestValidator(req, addr)

	def getServerSocket(self):
		return self.socket
	
		
class bcRequestHandler(SocketServer.BaseRequestHandler):
	def handle(self):
		Log.msg('BroadcastServer','incoming request from',str(self.client_address[0]))
		# request is a simple string
		cmd = self.request[0]
		if cmd==NS_SYSCMD_LOCATION:
			# somebody wants to know our location, give them our URI
			self.request[1].sendto(self.server.nameServerURI,self.client_address)
		elif cmd==NS_SYSCMD_SHUTDOWN:
			# we should die!?
			if self.server.ignoreShutdown:
				Log.msg('BroadcastServer','Shutdown ignored.')
				self.request[1].sendto('Shutdown request denied',self.client_address)
			else:
				Log.msg('BroadcastServer','Shutdown received.')
				print 'BroadcastServer received shutdown request... will shutdown shortly...'
				self.request[1].sendto('Will shut down shortly',self.client_address)
				self.server.shutdown=1
		else:
			Log.warn('BroadcastServer','Invalid command ignored:',cmd)

# The default BC request validator... accepts everything
# You must subclass this for your own validators
class BCReqValidator(object):
	def __call__(self, req, addr):
		(cmd,self.sock)=req
		self.addr=addr
		if cmd==NS_SYSCMD_LOCATION:
			return self.acceptLocationCmd()
		elif cmd==NS_SYSCMD_SHUTDOWN:
			return self.acceptShutdownCmd()
		else:
			return 0
	def reply(self,msg):
		self.sock.sendto(msg,self.addr)
	def acceptLocationCmd(self):
		return 1
	def acceptShutdownCmd(self):
		return 1


#############################################################################

class NameServerStarter(object):
	def __init__(self, identification=None):
		Pyro.core.initServer()
		self.persistent=False
		self.identification=identification
		self.started = Pyro.util.getEventObject()
	def start(self, *args, **kwargs):			# see _start for allowed arguments
		kwargs["startloop"]=1
		self._start( *args, **kwargs )
	def initialize(self, *args, **kwargs):		# see _start for allowed arguments
		kwargs["startloop"]=0
		self._start( *args, **kwargs )
	def getServerSockets(self):
		result=self.daemon.getServerSockets()
		if self.bcserver:
			result.append(self.bcserver.getServerSocket())
		return result
	def waitUntilStarted(self,timeout=None):
		self.started.wait(timeout)
		return self.started.isSet()
	def _start(self,hostname=None, nsport=None, bcport=0, keep=0, persistent=0, dbdir=None, Guards=(None,None), allowmultiple=0, dontlookupother=0, verbose=0, startloop=1, role=(Pyro.constants.NSROLE_SINGLE,None), bcaddr=None, nobroadcast=False ):
		if nsport is None:
			if role[0]==Pyro.constants.NSROLE_SECONDARY:
				nsport=Pyro.config.PYRO_NS2_PORT
			else:
				nsport=Pyro.config.PYRO_NS_PORT
		if not bcport:
			if role[0]==Pyro.constants.NSROLE_SECONDARY:
				bcport=Pyro.config.PYRO_NS2_BC_PORT
			else:
				bcport=Pyro.config.PYRO_NS_BC_PORT
		if not bcaddr:
			if role[0]==Pyro.constants.NSROLE_SECONDARY:
				bcaddr=Pyro.config.PYRO_NS2_BC_ADDR
			else:
				bcaddr=Pyro.config.PYRO_NS_BC_ADDR
		otherNSuri=None

		try:
			if not dontlookupother:
				retries=Pyro.config.PYRO_BC_RETRIES
				timeout=Pyro.config.PYRO_BC_TIMEOUT
				Pyro.config.PYRO_BC_RETRIES=1
				Pyro.config.PYRO_BC_TIMEOUT=0.7
				try:
					otherNSuri=NameServerLocator().detectNS(bcaddr=bcaddr)
				except Pyro.errors.PyroError:
					pass
				else:
					print 'The Name Server appears to be already running on this segment.'
					print '(host:',otherNSuri.address,' port:',otherNSuri.port,')'
					if allowmultiple:
						print 'WARNING: starting another Name Server in the same segment!'
					elif role[0] in (Pyro.constants.NSROLE_PRIMARY, Pyro.constants.NSROLE_SECONDARY):
						pass
					else:
						msg='Cannot start multiple Name Servers in the same network segment.'
						print msg
						raise Pyro.errors.NamingError(msg)
	
				if role[0]!=Pyro.constants.NSROLE_SINGLE:
					print "Locating twin NameServer."
					# Do this before starting our own daemon, otherwise possible deadlock!
					# This step is done here to make pretty certain that one of both name
					# servers finds the other either *now*, or else later on (below).
					# If we omit this step here, deadlock may occur on the attempt below!
					otherNS = self.locateTwinNS(role, otherNSuri)
					if otherNS:
						print "Found twin NameServer at",otherNS.URI.address,"port",otherNS.URI.port
						role=(role[0], otherNS)
		
				Pyro.config.PYRO_BC_RETRIES=retries
				Pyro.config.PYRO_BC_TIMEOUT=timeout
			daemon = Pyro.core.Daemon(host=hostname, port=nsport,norange=1)
		except Pyro.errors.DaemonError,x:
			print 'The Name Server appears to be already running on this host.'
			print '(or somebody else occupies our port,',nsport,')'
			if hostname:
				print 'It could also be that the address \''+hostname+'\' is not correct.'
			print 'Name Server was not started!'
			raise

		if self.identification:
			daemon.setAllowedIdentifications([self.identification])
			print 'Requiring connection authentication.'
		if Guards[0]:
			daemon.setNewConnectionValidator(Guards[0])

		if persistent:
			ns=PersistentNameServer(dbdir,role=role[0], identification=self.identification)
			daemon.useNameServer(ns)
			NS_URI=daemon.connectPersistent(ns,Pyro.constants.NAMESERVER_NAME)
			self.persistent=True
		else:
			ns=NameServer(role=role[0], identification=self.identification)
			daemon.useNameServer(ns)
			NS_URI=daemon.connect(ns,Pyro.constants.NAMESERVER_NAME)
			self.persistent=False

		self.bcserver=None
		if nobroadcast:
			Log.msg('NS daemon','Not starting broadcast server due to config option')
			if verbose:
				print "Not starting broadcast server."
		else:
			# Try to start the broadcast server. Binding on the magic "<broadcast>"
			# address should work, but on some systems (windows) it doesn't.
			# Therefore we first try "<broadcast>", if that fails, try "".
			# If any address override is in place, use that ofcourse.
			notStartedError=""
			msg = daemon.validateHostnameAndIP()
			if msg:
				Log.msg('NS daemon','Not starting broadcast server because of issue with daemon IP address.')
				if verbose:
					print "Not starting broadcast server."
			else:
				if bcaddr:
					broadcastAddresses=[bcaddr]
				else:
					broadcastAddresses=["<broadcast>", "", "255.255.255.255"]
				for bc_bind in broadcastAddresses:
					try:
						self.bcserver = BroadcastServer((bc_bind,bcport),bcRequestHandler,norange=1)
						break
					except socket.error,x:
						notStartedError += str(x)+" "
				if not self.bcserver:
					print 'Cannot start broadcast server. Is somebody else occupying our broadcast port?'
					print 'The error(s) were:',notStartedError
					print '\nName Server was not started!'
					raise Pyro.errors.NamingError("cannot start broadcast server")
		
				if Guards[1]:
					self.bcserver.setRequestValidator(Guards[1])
				self.bcserver.keepRunning(keep)

		if keep:
			ns.ignoreShutdown=True
			if verbose:
				print 'Will ignore shutdown requests.'
		else:
			ns.ignoreShutdown=False
			if verbose:
				print 'Will accept shutdown requests.'

			print 'Name server listening on:',daemon.sock.getsockname()
			if self.bcserver:
				print 'Broadcast server listening on:',self.bcserver.socket.getsockname()
			message = daemon.validateHostnameAndIP()
			if message:
				print "\nWARNING:",message,"\n"

		if Guards[0] or Guards[1]:
			if verbose:
				print 'Using security plugins:'
			if Guards[0]:
				clazz=Guards[0].__class__
				if verbose:
					print '  NS new conn validator =',clazz.__name__,'from', clazz.__module__, ' ['+sys.modules.get(clazz.__module__).__file__+']'
			elif verbose: print '  default NS new conn validator'
			if Guards[1]:
				clazz=Guards[1].__class__
				if verbose:
					print '  BC request validator  =',clazz.__name__,'from', clazz.__module__, ' ['+sys.modules.get(clazz.__module__).__file__+']'
			elif verbose: print '  default BC request validator'

		ns.publishURI(NS_URI,verbose)

		if self.bcserver:
			self.bcserver.setNS_URI(NS_URI)
		Log.msg('NS daemon','This is the Pyro Name Server.')
		if persistent:
			Log.msg('NS daemon','Persistent mode, database is in',ns.getDBDir())
			if verbose:
				print 'Persistent mode, database is in',ns.getDBDir()
		Log.msg('NS daemon','Starting on',daemon.hostname,'port', daemon.port)
		if self.bcserver:
			Log.msg('NS daemon','Broadcast server on port',bcport)
		else:
			Log.msg('NS daemon','No Broadcast server')

		if role[0]==Pyro.constants.NSROLE_PRIMARY:
			print "Primary",
		elif role[0]==Pyro.constants.NSROLE_SECONDARY:
			print "Secondary",
		print 'Name Server started.'

		# If we run in primary or secondary mode, resynchronize
		# the NS database with the other name server.
		# Try again to look it up if it wasn't found before.
		
		if role[0]!=Pyro.constants.NSROLE_SINGLE:
			if not otherNS:
				# try again to contact the other name server
				print "Locating twin NameServer again."
				otherNS = self.locateTwinNS(role, otherNSuri)
				role=(role[0], otherNS)
			if otherNS:
				# finally got it, resync!
				print "Found twin NameServer at",otherNS.URI.address,"port",otherNS.URI.port
				ns._initialResyncWithTwin(otherNS)

		self.started.set()   # signal that we've started (for external threads)
		
		self.daemon=daemon
		if os.name!="java":
			daemon.setTimeout(20)

		if startloop:
			# I use a timeout here otherwise you can't break gracefully on Windoze
			try:
				if self.bcserver:
					daemon.requestLoop(lambda s=self: not s.bcserver.shutdown,
						self.bcserver.preferredTimeOut,[self.bcserver],self.bcserver.bcCallback)
					if self.bcserver.shutdown:
						self.shutdown(ns)
				else:
					daemon.requestLoop()
			except KeyboardInterrupt:
				Log.warn('NS daemon','shutdown on user break signal')
				print 'Shutting down on user break signal.'
				self.shutdown(ns)
			except:
				try:
					(exc_type, exc_value, exc_trb) = sys.exc_info()
					out = ''.join(traceback.format_exception(exc_type, exc_value, exc_trb)[-5:])
					Log.error('NS daemon', 'Unexpected exception, type',exc_type,
						'\n--- partial traceback of this exception follows:\n',
						out,'\n--- end of traceback')
					print '*** Exception occured!!! Partial traceback:'
					print out
					print '*** Resuming operations...'
				finally:	
					del exc_type, exc_value, exc_trb    # delete frame refs to allow proper GC

			Log.msg('NS daemon','Shut down gracefully.')
			print 'Name Server gracefully stopped.'


	def locateTwinNS(self, role, otherNSuri):
		try:
			retries=Pyro.config.PYRO_BC_RETRIES
			timeout=Pyro.config.PYRO_BC_TIMEOUT
			Pyro.config.PYRO_BC_RETRIES=1
			Pyro.config.PYRO_BC_TIMEOUT=1
			try:
				if role[1]:
					(host,port)=(role[1]+':').split(':')[:2]
					if len(port)==0:
						port=None
					else:
						port=int(port)
					otherNS=NameServerLocator(self.identification).getNS(host,port,trace=0)
				else:
					if otherNSuri:
						otherNS=NameServerLocator(self.identification).getNS(host=otherNSuri.address, port=otherNSuri.port, trace=0)
					else:
						if role[0]==Pyro.constants.NSROLE_PRIMARY:
							port=Pyro.config.PYRO_NS2_BC_PORT
						else:
							port=Pyro.config.PYRO_NS_BC_PORT
						otherNS=NameServerLocator(self.identification).getNS(host=None,port=port,trace=0)
				Log.msg("NameServerStarted","Found twin NS at",otherNS.URI)
				return otherNS
			except Pyro.errors.ConnectionDeniedError,x:
				raise
			except Exception,x:
				print "WARNING: Cannot find twin NS yet: ",x
				Log.msg("NameServerStarter","Cannot find twin NS yet:",x)
				return None
		finally:
			Pyro.config.PYRO_BC_RETRIES=retries
			Pyro.config.PYRO_BC_TIMEOUT=timeout
			

	def handleRequests(self,timeout=None):
		# this method must be called from a custom event loop
		if self.bcserver:
			self.daemon.handleRequests(timeout, [self.bcserver], self.bcserver.bcCallback)
			if self.bcserver.shutdown:
				self.shutdown()
		else:
			self.daemon.handleRequests(timeout)

	def shutdown(self, ns=None):
		if ns:
			# internal shutdown call with specified NS object
			daemon=ns.getDaemon()
		else:
			# custom shutdown call w/o specified NS object, use stored instance
			daemon=self.daemon
			ns=daemon.getNameServer()
			del self.daemon
		ns._removeTwinNS()
		if not self.persistent:
			daemon.disconnect(ns) # clean up nicely only if not running in persistent mode
		if self.bcserver:
			self.bcserver.shutdown=1
		daemon.shutdown()

def main(argv):
	Args = Pyro.util.ArgParser()
	Args.parse(argv,'hkmrvxn:p:b:c:d:s:i:1:2:')
	if Args.hasOpt('h'):
		print 'Usage: pyro-ns [-h] [-k] [-m] [-r] [-x] [-n hostname] [-p port] [-b bcport] [-c bcaddr]'
		print '          [-i identification] [-d [databaselocation]] [-s securitymodule]'
		print '          [-1 [host:port]] [-2 [host:port]] [-v]'
		print '  where -p = NS server port (0 for auto)'
		print '        -n = non-default hostname to bind on'
		print '        -b = NS broadcast port'
		print '        -c = NS broadcast address override'
		print '        -x = do not start a broadcast listener'
		print '        -m = allow multiple instances in network segment'
		print '        -r = don\'t attempt to find already existing nameservers'
		print '        -k = keep running- do not respond to shutdown requests'
		print '        -d = use persistent database, provide optional storage directory'
		print '        -s = use given python module with security plugins'
		print '        -i = specify the required authentication ID'
		print '        -1 = runs this NS as primary, opt. specify where secondary is'
		print '        -2 = runs this NS as secondary, opt. specify where primary is'
		print '        -v = verbose output'
		print '        -h = print this help'
		raise SystemExit
	host = Args.getOpt('n',None)
	port = Args.getOpt('p',None)
	if port:
		port=int(port)
	bcport = int(Args.getOpt('b',0))
	bcaddr = Args.getOpt('c',None)
	nobroadcast = Args.hasOpt('x')
	
	role=Pyro.constants.NSROLE_SINGLE
	roleArgs=None
	if Args.hasOpt('1'):
		role=Pyro.constants.NSROLE_PRIMARY
		roleArgs=Args.getOpt('1')
	if Args.hasOpt('2'):
		role=Pyro.constants.NSROLE_SECONDARY
		roleArgs=Args.getOpt('2')

	ident = Args.getOpt('i',None)
	verbose = Args.hasOpt('v')
	keep=Args.hasOpt('k')
	allowmultiple=Args.hasOpt('m')
	dontlookupother=Args.hasOpt('r')

	try:
		dbdir = Args.getOpt('d')
		persistent = 1
	except KeyError:
		persistent = 0
		dbdir = None

	try:
		secmod = __import__(Args.getOpt('s'),locals(),globals())
		Guards = (secmod.NSGuard(), secmod.BCGuard())
	except ImportError,x:
		print 'Error loading security module:',x
		print '(is it in your python import path?)'
		raise SystemExit
	except KeyError:
		secmod = None
		Guards = (None,None)

	Args.printIgnored()
	if Args.args:
		print 'Ignored arguments:', ' '.join(Args.args)

	print '*** Pyro Name Server ***'
	if ident:
		starter=NameServerStarter(identification=ident)
	else:
		starter=NameServerStarter()

	try:
		starter.start(host,port,bcport,keep,persistent,dbdir,Guards,allowmultiple,dontlookupother,verbose,role=(role,roleArgs),bcaddr=bcaddr,nobroadcast=nobroadcast)
	except (Pyro.errors.NamingError, Pyro.errors.DaemonError),x:
		# this error has already been printed, just exit.
		pass


# allow easy starting of the NS by using python -m
if __name__=="__main__":
	main(sys.argv[1:])

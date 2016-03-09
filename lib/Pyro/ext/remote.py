#############################################################################
#
#     simple Pyro connection module, originally written by John Wiegley
#
#     This is part of "Pyro" - Python Remote Objects
#     which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import UserDict
import exceptions
import os
import re
import signal
import socket
import sys
import time
import types

import Pyro.errors
import Pyro.naming
import Pyro.core
import Pyro.util

from Pyro.protocol import ProtocolError

true, false = 1, 0

copy_types         = false
verbose            = false
pyro_nameserver    = None
pyro_daemon        = None
client_initialized = false
server_initialized = false
daemon_host        = ''
daemon_port        = 0
daemon_objects     = []
daemon_types       = []

def tb_info(tb):
	codename = tb.tb_frame.f_code.co_filename
	lineno   = tb.tb_lineno
	if not (codename == '<string>' or codename.find(".py") > 0):
		lineno = lineno - 2
	return lineno, codename

def canonize(e_type, e_val, e_traceback):
	"Turn the exception into a textual representation."
	# find the last traceback:
	tb = e_traceback

	lineno, codename = tb_info(tb)
	lines = [ "%s %s" % (codename, lineno) ]

	found = None
	if tb.tb_frame.f_code.co_filename[0] == '<':
		found = tb

	while tb.tb_next:
		tb = tb.tb_next
		if tb.tb_frame.f_code.co_filename[0] == '<':
			found = tb
		lineno, codename = tb_info(tb)
		lines.append("%s %s" % (codename, lineno))

	if found:
		tb = found

	lineno, codename = tb_info(tb)

	if codename == '<string>':
		lines.insert(0, "%s in command: %s" % (e_type, e_val))
	elif codename.find(".py") > 0 and e_type == "SyntaxError":
		lines.insert(0, "%s in: %s" % (e_type, e_val))
	else:
		lines.insert(0, "%s in line %s of %s: %s" %
					 (e_type, lineno, codename, e_val))

	return lines

def exception_text():
	return sys.exc_value

def format_exception():
	return canonize(*sys.exc_info())

def register_type(t):
	"""Whenever type T goes in or out, wrap/unwrap the type so that
	the user is always interacting with the server object, or the
	server interacts with the object directly."""
	if t not in daemon_types:
		daemon_types.append(t)

def unregister_objects():
	if pyro_daemon:
		global daemon_objects
		for obj in daemon_objects:
			try: pyro_daemon.disconnect(obj)
			except: pass
		daemon_objects = []

sys.exitfunc = unregister_objects

def host_ipaddr(interface = None):
	if sys.platform == "win32":
		return socket.gethostbyname(socket.gethostname())

	cmd = "/sbin/ifconfig"
	if interface:
		cmd = '%s %s' % (cmd, interface)
	fd = os.popen(cmd)

	this_host  = None
	interfaces = {}
	name       = None

	for line in fd.readlines():
		match = re.match("(\S+)", line)
		if match: name = match.group(1)
		match = re.search("inet addr:(\S+)", line)
		if match:
			addr = match.group(1)
			if name:
				interfaces[name] = addr

	if interfaces.has_key(interface):
		this_host = interfaces[interface]
	else:
		for name, addr in interfaces.items():
			if re.match("ppp", name):
				this_host = addr
				break
			elif re.match("eth", name):
				this_host = addr

	fd.close()

	return this_host or socket.gethostbyname(socket.gethostname())

def find_nameserver(hostname = None, portnum = None):
	if hostname and hostname.find('://') > 0:
		URI = Pyro.core.PyroURI(hostname)
		ns  = Pyro.naming.NameServerProxy(URI)
	else:
		try:
			if verbose:
				print 'Searching for Naming Service on %s:%d...' % \
					(hostname or 'BROADCAST',
					 portnum or Pyro.config.PYRO_NS_BC_PORT)
			locator = Pyro.naming.NameServerLocator()
			ns = locator.getNS(host = hostname, port = portnum)

		except (Pyro.core.PyroError, socket.error), x:
			localhost = socket.gethostbyname('localhost')
			if verbose:
				print "Error:", x
				print """
Naming Service not found with broadcast.
Trying local host""", localhost, '...',

			ns = locator.getNS(host = localhost, port = portnum)

	if verbose: print 'Naming Service found at', ns.URI

	return ns

class Error(Exception): pass

class ObjBase(Pyro.core.ObjBase):
	"""This extension of Pyro.core.ObjBase makes sure that any values
	that get returned to the caller which are of a significant type,
	get wrapped first in proxies.

	Likewise, if a proxy class comes back to us, and it's in regard to
	an object native to this server, unwrap it."""
	def __nonzero__(self): return 1

	def Pyro_dyncall(self, method, flags, args):
		try:
			base = Pyro.core.ObjBase.Pyro_dyncall
			result = wrap(base(self, method, flags, unwrap(args)))
		except:
			result = Error('\n'.join(format_exception()))
		return result

	def _r_ga(self, attr):
		return wrap(Pyro.core.ObjBase._r_ga(self, attr))

	def _r_sa(self, attr, value):
		Pyro.core.ObjBase._r_sa(self, attr, unwrap(value))

class Nameserver:
	"""This helper class allows the server to use Pyro's naming
	service for publishing certain objects by name.  It integrates
	better with remote.py, than Pyro.naming.NameServer does."""
	def __init__(self, ns, ns_port):
		self.ns      = ns
		self.ns_port = ns_port

	def __cmp__(self, other):
		return self.ns == other.ns and self.ns_port == other.ns_port

	def __str__(self):
		if self.ns_port:
			return "%s:%s" % (self.ns, self.ns_port)
		return self.ns

	def resolve(self, name):
		return get_remote_object(name, self.ns, self.ns_port)

	def register(self, name, object):
		return provide_local_object(object, name, self.ns, self.ns_port)

	def unregister(self, object):
		for obj in daemon_objects[:]:
			if obj.delegate is object:
				pyro_daemon.disconnect(obj)
				daemon_objects.remove(obj)

class DynamicProxy(Pyro.core.DynamicProxyWithAttrs):
	"""This version of the proxy just wraps args before making
	external calls."""
	def __nonzero__(self):
		return true

	def _invokePYRO(self, *vargs, **kargs):
		result = unwrap(apply(Pyro.core.DynamicProxyWithAttrs._invokePYRO,
							  tuple([self] + wrap(list(vargs))), wrap(kargs)))
	
		if type(result) is types.InstanceType and \
		   isinstance(result, Error) or \
		   isinstance(result, Pyro.errors.PyroError) or \
		   isinstance(result, ProtocolError):
			msg = str(result)
			type_name = msg[: msg.find(' ')]

			if type_name == 'exceptions.IndexError':
				try:
					real_type = eval(type_name)
					msg       = msg.split('\n')[0]
					result    = real_type(msg[msg.find(':') + 2 :])
				except:
					pass

			raise result
		else:
			return result

def unwrap(value):
	t = type(value)
	if t is types.InstanceType and isinstance(value, DynamicProxy):
		if pyro_daemon:
			try:
				return pyro_daemon.getLocalObject(value.objectID)
			except KeyError:
				pass
		return value
	elif t is types.ListType:
		for i in range(len(value)):
			value[i] = unwrap(value[i])
	elif t is types.TupleType:
		value = list(value)
		for i in range(len(value)):
			value[i] = unwrap(value[i])
		return tuple(value)
	elif t is types.DictType:
		for k, v in value.items():
			value[k] = unwrap(v)
	return value

def wrap(value):
	"""Wrap the argument, returning a copy -- since otherwise we might
	alter a local data structure inadvertantly."""
	t = type(value)
	if t is types.InstanceType:
		matched = false
		for dt in daemon_types:
			if isinstance(value, dt):
				matched = true
		if not copy_types and not matched and \
			   not isinstance(value, DynamicProxy):
			return provide_local_object(value)
	elif t is types.ListType:
		value = value[:]
		for i in range(len(value)):
			value[i] = wrap(value[i])
	elif t is types.TupleType:
		value = list(value)
		for i in range(len(value)):
			value[i] = wrap(value[i])
		return tuple(value)
	elif t is types.DictType:
		copy = {}
		for k, v in value.items():
			copy[k] = wrap(v)
		return copy
	return value

def get_remote_object(name, hostname = None, portnum = None):
	global client_initialized, pyro_nameserver

	# initialize Pyro -- Python Remote Objects
	if not client_initialized:
		Pyro.core.initClient(verbose)
		client_initialized = true

	if pyro_nameserver is None or hostname:
		pyro_nameserver = find_nameserver(hostname, portnum)

	if verbose:
		print 'Binding object %s' % name

	try:
		URI = pyro_nameserver.resolve(name)
		if verbose:
			print 'URI:', URI

		return DynamicProxy(URI)

	except Pyro.core.PyroError, x:
		raise Error("Couldn't bind object, nameserver says:", x)

class Cache(UserDict.UserDict):
	"""simple cache that uses least recently accessed time to trim size"""
	def __init__(self,data=None,size=100):
		UserDict.UserDict.__init__(self,data)
		self.size = size

	def resize(self):
		"""trim cache to no more than 95% of desired size"""
		trim = max(0, int(len(self.data)-0.95*self.size))
		if trim:
			# don't want self.items() because we must sort list by access time
			values = map(None, self.data.values(), self.data.keys())
			values.sort()
			for val,k in values[0:trim]:
				del self.data[k]

	def __setitem__(self,key,val):
		if (not self.data.has_key(key) and
			len(self.data) >= self.size):
			self.resize()
		self.data[key] = (time.time(), val)

	def __getitem__(self,key):
		"""like normal __getitem__ but updates time of fetched entry"""
		val = self.data[key][1]
		self.data[key] = (time.time(),val)
		return val

	def get(self,key,default=None):
		"""like normal __getitem__ but updates time of fetched entry"""
		try:
			return self[key]
		except KeyError:
			return default

	def values(self):
		"""return values, but eliminate access times first"""
		vals = list(self.data.values())
		for i in range(len(vals)):
			vals[i] = vals[i][1]
		return tuple(vals)

	def items(self):
		return map(None, self.keys(), self.values())

	def copy(self):
		return self.__class__(self.data, self.size)

	def update(self, otherdict):
		for k in otherdict.keys():
			self[k] = otherdict[k]

provided_objects = Cache(size = 100)

def provide_local_object(obj, name = None, hostname = None, portnum = None):
	global server_initialized, pyro_daemon, pyro_nameserver

	proxy_class = DynamicProxy

	if not server_initialized:
		Pyro.core.initServer(verbose)
		server_initialized = true

	if pyro_daemon is None:
		pyro_daemon = Pyro.core.Daemon(host = daemon_host,
									   port = daemon_port)

	# If no 'name' was specified, don't even bother with the
	# nameserver.
	if name:
		if pyro_nameserver is None or hostname:
			pyro_nameserver = find_nameserver(hostname, portnum)

		pyro_daemon.useNameServer(pyro_nameserver)

		if verbose:
			print 'Remoting object', name

			# tell nameserver to forget any earlier use of this name
		try:
			if pyro_nameserver.resolve(name):
				pyro_nameserver.unregister(name)
		except Pyro.errors.NamingError:
			pass

	if not isinstance(obj, Pyro.core.ObjBase):
		if provided_objects.has_key(obj):
			obj = provided_objects[obj]
		else:
			slave = ObjBase()
			slave.delegateTo(obj)
			provided_objects[obj] = slave
			obj = slave

	URI = pyro_daemon.connect(obj, name)
	daemon_objects.append(obj)

	proxy = proxy_class(URI)

	return proxy

abort = false

def interrupt(*args):
	global abort
	abort = true

if hasattr(signal,'SIGINT'): signal.signal(signal.SIGINT, interrupt)
#if hasattr(signal,'SIGHUP'): signal.signal(signal.SIGHUP, interrupt)
#if hasattr(signal,'SIGQUIT'): signal.signal(signal.SIGQUIT, interrupt)

def handle_requests(wait_time = None, callback = None):
	global abort

	abort = false

	if pyro_daemon is None:
		raise Error("There is no daemon with which to handle requests")

	if wait_time:
		start = time.time()

	while not abort:
		try:
			pyro_daemon.handleRequests(wait_time)

			if wait_time:
				now = time.time()
				if callback and now - start > wait_time:
					callback()
					start = now
			elif callback:
				callback()

		# ignore socket and select errors, they are often transient
		except socket.error: pass
		except Exception, msg:
			if verbose:
				print "Error:", sys.exc_type, msg
			abort = true
		except:
			abort = true

	return abort

def handle_requests_unsafe(wait_time = None, callback = None):
	global abort

	abort = false

	if pyro_daemon is None:
		raise Error("There is no daemon with which to handle requests")

	if wait_time:
		start = time.time()

	while 1:
		pyro_daemon.handleRequests(wait_time)

		if wait_time:
			now = time.time()
			if callback and now - start > wait_time:
				callback()
				start = now
		elif callback:
			callback()

	return true

def unregister_object(obj):
	if pyro_daemon:
		try: pyro_daemon.disconnect(obj)
		except: pass
		global daemon_objects
		if obj in daemon_objects:
			daemon_objects.remove(obj)

#############################################################################
#
#	Pyro Exception Types
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

#############################################################################
# PyroError is the Pyro exception type which is used for problems WITHIN Pyro.
# User code should NOT use it!!
#
# NOTE: Any exception occuring in the user code on the server will be catched
# and transported to the client, where it is raised just as if it occured
# locally. The occurrence is logged in the server side Pyro log.
# Pyro will use the [Remote]PyroError exceptions and their subtypes to
# indicate that an internal problem occured.
#############################################################################

class PyroError(Exception):     pass		# internal

class URIError(PyroError):      pass		# URI probs
class DaemonError(PyroError):   pass		# daemon probs
class ProtocolError(PyroError): pass		# protocol adapter
class ConnectionClosedError(ProtocolError): pass	# connection in adapter is closed
class ConnectionDeniedError(ProtocolError): pass	# server refused connection
class TimeoutError(ConnectionClosedError): pass		# communication timeout
class NamingError(PyroError):   pass		# name server
class NoModuleError(PyroError):	pass		# no module found for incoming obj

# do NOT use the following yourself:
class _InternalNoModuleError(PyroError):	
	def __init__(self, modulename=None, fromlist=None, *args):
		# note: called without args on Python 2.5+, args will be set by __setstate__
		self.modulename=modulename
		self.fromlist=fromlist
		PyroError.__init__(* (self,)+args)
	def __getstate__(self):
		return { "modulename": self.modulename, "fromlist": self.fromlist }
	def __setstate__(self, state):
		self.modulename=state["modulename"]
		self.fromlist=state["fromlist"]


#############################################################################
#
#	PyroExceptionCapsule - Exception encapsulation.
#
#	This class represents a Pyro exception which can be transported
#	across the network, and raised on the other side (by invoking raiseEx).
#	NOTE: the 'real' exception class must be 'known' on the other side!
#	NOTE2: this class is adapted from exceptions.Exception.
#	NOTE3: PyroError IS USED FOR ACTUAL PYRO ERRORS. PyroExceptionCapsule
#          IS ONLY TO BE USED TO TRANSPORT AN EXCEPTION ACROSS THE NETWORK.
#	NOTE4: It sets a special attribute on the exception that is raised
#	       (constants.TRACEBACK_ATTRIBUTE), this is the *remote* traceback 
#   NOTE5: ---> this class is intentionally not subclassed from Exception,
#               and also not from object.
#               Pyro's exception handling depends on this!
#
#############################################################################

import Pyro.constants

class PyroExceptionCapsule:				# don't make this a new style class
	def __init__(self,excObj,args=None):
		self.excObj = excObj
		self.args=args  # if specified, this is the remote traceback info
	def raiseEx(self):
		setattr(self.excObj,Pyro.constants.TRACEBACK_ATTRIBUTE,self.args)
		raise self.excObj
	def __str__(self):
		s=self.excObj.__class__.__name__
		if not self.args:
			return s
		elif len(self.args) == 1:
			return s+': '+str(self.args[0])
		else:
			return s+': '+str(self.args)
	def __getitem__(self, i):
		return self.args[i]	

#############################################################################
#
#	Pyro Utilities (part 2, to avoid circular dependencies)
#	User code should never import this, always use Pyro.util!
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

_supports_mt=None
_supports_comp=None

def supports_multithreading():
	global _supports_mt
	if _supports_mt is None:
		try:
			from threading import Thread, Lock
			_supports_mt=1
		except:
			_supports_mt=0
	return _supports_mt
	
def supports_compression():
	global _supports_comp
	if _supports_comp is None:
		try:
			import zlib
			_supports_comp=1
		except:
			_supports_comp=0
	return _supports_comp

if supports_multithreading():
	import threading

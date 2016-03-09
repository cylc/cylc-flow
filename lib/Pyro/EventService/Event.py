#############################################################################
#  
#	Event Service client base classes
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import time

# EVENT - the thing that is published. Has a subject and contains a message.
class Event(object):
	def __init__(self, subject, msg, creationTime=None):
		self.msg=msg
		self.subject=subject
		self.time=creationTime or time.time()
	def __str__(self):
		return "<EVENT SUBJ %s (%s): %s>" % (self.subject, time.ctime(self.time), str(self.msg))

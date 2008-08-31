#!/usr/bin/python

"""
allow class instantiation by name, without using eval

E.g.:

##foo.py:
class bar:
	def __init__( self, str ):
		self.greeting = str

	def greet( self ):
		print self.greeting

##main.py:
baz = class_from_module( "foo", "bar" )("hello")
baz.greet()
"""

def class_from_module( module, class_name ):
	mod = __import__( module )
	return getattr( mod, class_name)

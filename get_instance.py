#!/usr/bin/python

"""
class instantiation by module and class name

E.g.:

##foo.py:
class bar:
	def __init__( self, str ):
		self.greeting = str

	def greet( self ):
		print self.greeting

##main.py:
baz = get_instance( "foo", "bar" )("hello")
baz.greet()
"""

def get_instance( module, class_name ):
	mod = __import__( module )
	return getattr( mod, class_name)

#!/usr/bin/python

# object instantiation by module and class name

def get_by_name( module, class_name ):
	mod = __import__( module )
	return getattr( mod, class_name)

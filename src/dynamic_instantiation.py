#!/usr/bin/python

def get_object( module_name, class_name ):
    mod = __import__( module_name )
    return getattr( mod, class_name)

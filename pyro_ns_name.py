#!/usr/bin/python

from config import pyro_ns_group

"""generate a Pyro nameserver name from an object name"""

def pyro_object_name( object_name ):
    return pyro_ns_group + '.' + object_name

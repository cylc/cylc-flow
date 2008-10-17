#!/usr/bin/python

# Different controller instances must use different versions of this
# file, each with pyro_ns_group set to a different group name, because
# there can be only one instance of the nameserver running at a time.

# See Pyro manual for nameserver hierachical naming details ...
# prepending ':' put names or sub-groups under the root group. 
 
from config import pyro_ns_group

def pyro_ns_name( object_name ):
   return pyro_ns_group + '.' + object_name

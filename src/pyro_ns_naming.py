#!/usr/bin/python

# Different sequenz instances must use different Pyro nameserver 
# group names to prevent the different systems interfering with
# each other via the common nameserver. 

# See Pyro manual for nameserver hierachical naming details ...
# prepending ':' puts names or sub-groups under the root group. 
 
def name( object_name, group_name ):
   return group_name + '.' + object_name

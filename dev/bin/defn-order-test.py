#!/usr/bin/env python

import time, string, random
from copy import deepcopy

"""
This is a standalone performance test of the algorithm used in gcylc to 
sort namespaces into "definition order", i.e. the order in which they are
defined in the suite.rc file.
"""

# Number of namespaces.
N=10000

# N names of length 5-15 characters each (c.f. namespaces in "definition
# order").
names = []
for i in range(0,N):
    names.append( ''.join( random.choice(string.ascii_letters) for n in xrange( 5+random.randrange(10) )))

# N lists with 2-7 names each (c.f. tree view paths of the inheritance
# hierarchy).
paths1 = []
for i in range(0,N):
    p = []
    for j in range(0, 2+random.randrange(6)):
        z = random.randrange(0,N)
        p.append( names[z] )
    paths1.append(p)

paths2 = deepcopy( paths1 )

# Alphanumeric sort.
s = time.time()
paths1.sort()
t1 = time.time() - s

dict_names = dict( zip( names, range(0,len(names))))

# Definition order sort.
s = time.time()
paths2.sort( key=lambda x: map( dict_names.get, x ) )
t2 = time.time() - s

print "Alphanumeric sort:", t1, "sec"
print "Definition sort:", t2, "sec"
print " => factor of", t2/t1


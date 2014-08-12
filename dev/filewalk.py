#!/usr/bin/env python

# How to traverse a directory tree using Python

import os, re

pwd = os.getcwd()
match = os.path.join( 'CRAP', 'JUNK', 'foo', 'YYYYMMDDHH', 'foo', 'munge.*' )
print match
cpts = re.split( '/', match )

pre = ''
for cpt in cpts:
    print '*', cpt
    if re.search( 'YYYY', cpt ):
        break
    else:
        pre = os.path.join( pre, cpt )

print pre

for root, dirs, files in os.walk( pre ):
    print ':::', root, dirs, files

    index = len( re.split('/', root ))
    print index, cpts[index]

    mfoo = re.sub( 'YYYYMMDDHH', '(\d{10})', cpts[index] )

    ddirs = dirs
    for dir in ddirs:
        if not re.match( mfoo, dir ):
            print 'rejecting', dir
            dirs.remove( dir )

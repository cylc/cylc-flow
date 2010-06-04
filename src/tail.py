#!/usr/bin/python

import sys
import time

def tail( file ):
    interval = 1.0

    while True:
        where = file.tell()
        line = file.readline()
        if not line:
            time.sleep( interval )
            file.seek( where )
        else:
            yield line

#for line in tail( open( sys.argv[1] )):
#    print line,

#!/usr/bin/env python

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
            yield None  # return even if no new line
                        # so the host thread doesn't 
                        # hang with 'cylc view' exits.
        else:
            yield line

# FOR NORMAL 'tail -F' behaviour:
#def tail( file ):
#    interval = 1.0
#
#    while True:
#        where = file.tell()
#        line = file.readline()
#        if not line:
#            time.sleep( interval )
#            file.seek( where )
#        else:
#            yield line
#
#for line in tail( open( sys.argv[1] )):
#    print line,

#!/usr/bin/env python

# This illustrates the batch processing paradigm used in the cylc 
# housekeeping utility.

import os
from subprocess import Popen

def process( batch, batchno ):
    print "Batch No.", batchno
    proc = []
    for item in batch:
        print 'spawning', item 
        proc.append( Popen( item ) )
    for p in proc:
        # This blocks until p finishes:
        p.wait()
        # We could use p.poll() instead (returns None until 
        # p finishes, then the exit status); this would allow
        # print out of exactly when each process finishes. 
        # Same result in the end though, for whole batch wait.

if __name__ == "__main__":
    cmd = os.path.join( os.environ['CYLC_DIR'], 'dev', 'batch', 'foo.sh' )
    size = 3
    batch = []
    batchno = 0
    for i in range(0,10):
        if len( batch ) < size:
            # construct batch
            batch.append( [cmd, str(i)] )
            continue
        # batch full: process it.
        batchno += 1
        process( batch, batchno )
        batch = []
    # now process any leftovers
    batchno += 1
    process( batch, batchno )

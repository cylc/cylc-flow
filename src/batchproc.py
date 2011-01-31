#!/usr/bin/env python

import sys
from subprocess import Popen

class batchproc:
    """ Batch process items that return a subprocess-style command list
        [command, arg1, arg2, ...] via an execute() method. Items are
        added until a batch fills up, then the whole batch is processed
        in parallel and we wait on the whole batch to complete before
        beginning the next batch.  
        Users should do a final call to process() to handle any final
        items in an incomplete batch."""

    def __init__( self, size=1, verbose=False, shell=False ):
        self.batchno = 0
        self.items = []
        self.size = int(size)
        self.shell = shell
        self.verbose = verbose
        if verbose:
            print "Initializing batch processing, batch size", size

    def add_or_process( self, item ):
        self.items.append( item )
        if len( self.items ) >= self.size:
            self.batchno += 1
            self.process()
            self.items = []

    def process( self ):
        if self.verbose:
            print "Process Batch No.", self.batchno
        proc = []
        for item in self.items:
            #print 'spawning', item 
            proc.append( Popen( item.execute(), shell=self.shell ))
        for p in proc:
            # This blocks until p finishes:
            p.wait()
            # We could use p.poll() instead (returns None until 
            # p finishes, then the exit status); this would allow
            # print out of exactly when each process finishes. 
            # Same result in the end though, for whole batch wait.



#========= test code follows: ========>

class item:
    def __init__( self, i ):
        self.i = str(i)
    def execute( self ):
        return 'echo hello from ' + self.i + '... && sleep 5 && echo ... bye from ' + self.i

if __name__ == "__main__":

    usage = "USAGE: " + sys.argv[0] + " <batch-size>"
    if len( sys.argv ) != 2:
        print usage
        sys.exit(1)

    batchsize = sys.argv[1]

    b = batchproc( batchsize, shell=True )
    for i in range(0,10):
        b.add_or_process( item(i) )
    # process any leftovers
    b.process()


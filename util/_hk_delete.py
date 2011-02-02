#!/usr/bin/env python

from housekeeping import HousekeepingError, NonIdenticalTargetError
from hkdiff import diff
import os, sys

class hk_delete:
    """
        Delete a source item (file or directory).
        If a target directory is specified:
         + Delete only if a target item exists and is identical to the source.
         + Do not delete if the target item does not exist.
         + Do not delete, and Warn, if the target exists but differs from the source.
    """
 
    def __init__( self, src, tdir=None, verbose=False, cheap=False ):
        self.cheap = cheap
        self.verbose = verbose
        self.src = src
        self.tdir = tdir

        # source file/dir must exist
        if not os.path.exists( src ):
            raise HousekeepingError, "File not found: " + src

    def execute( self ):
        print "Delete:"
        print " + source: " + self.src
        if self.tdir:
            target = os.path.join( self.tdir, os.path.basename(src))
            print " + target: " + target

        if self.tdir:
            if not os.path.exists( target ):
                print "NOT DELETING: target does not exist"
                return
            else: 
                try:
                    diff( self.src, target, verbose=self.verbose, cheap=self.cheap ).execute()
                except NonIdenticalTargetError, x:
                    print 'NOT DELETING: target differs from source'
                    print >> sys.stderr, 'WARNING: target differs from source!'
                    return
                else:
                    # target is identical
                    print "DELETING: target exists"

        if os.path.isdir( self.src ):
            # delete directory tree
            shutil.rmtree( self.src )
        elif os.path.isfile( self.src ):
            # delete file
            os.unlink( self.src )
        print "SUCCEEDED"
        return
                
if __name__ == "__main__":
    usage = "USAGE: " + sys.argv[0] + " SRC [DIR] [-v]"

    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print usage
        sys.exit(1)

    verbose = False
    tdir = None
    src = sys.argv[1]

    if len(sys.argv) == 3:
        if sys.argv[2] == '-v':
            verbose = True
        else:
            tdir = sys.argv[2]
    elif len(sys.argv) == 4:
        if sys.argv[3] == '-v':
            verbose = True
        else:
            print usage
            sys.exit(1)
        tdir = sys.argv[2]
 
    hk_delete( src, tdir, verbose ).execute()

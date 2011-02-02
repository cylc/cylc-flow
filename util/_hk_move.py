#!/usr/bin/env python

from housekeeping import HousekeepingError, NonIdenticalTargetError
from mkdir_p import mkdir_p
from hkdiff import diff
from shutil import move
import subprocess
import os, sys

class hk_move:
    """
        Move a source item (file or directory) into a target directory.
         + Move only if the target item does not already exist.
         + Do not move if the target item already exists.
         + Warn if the target item exists but differs from the source.
    """
    def __init__( self, src, tdir, verbose=False, cheap=False ):
        self.cheap = cheap
        self.verbose = verbose
        self.src = src
        self.tdir = tdir

        # source file/dir must exist
        if not os.path.exists( src ):
            raise HousekeepingError, "File not found: " + src

        # create target dir if necessary
        if not os.path.exists( tdir ):
            mkdir_p( tdir )
        elif not os.path.isdir( tdir ):
            raise HousekeepingError, "Destination dir is a file: " + tdir

        # construct target
        self.target = os.path.join( tdir, os.path.basename(src))

    def execute( self ):
        print "Move:"
        print " + source: " + self.src
        print " + target: " + self.target

        if os.path.exists( self.target ):
            # target already exists, check if identical
            try:
                diff( self.src, self.target, verbose=self.verbose, cheap=self.cheap ).execute()
            except NonIdenticalTargetError, x:
                print 'NOT MOVING: target exists'
                print >> sys.stderr, 'WARNING: target differs from source!'
                return
            else:
                # target is identical, job done.
                print "NOT MOVING: target exists"
                return

        # target does not exist yet; OK to move.

        # shutil.move() is SAFE, docs say:
        #   Recursively move a file or directory to another location.
        #   If the destination is on the current filesystem, then simply
        #   use rename. Otherwise, copy src (with copy2()) to the dst
        #   and then remove src.
        move( self.src, self.tdir )
        print "SUCCEEDED"
        return
                
if __name__ == "__main__":
    usage = "USAGE: " + sys.argv[0] + " SRC DIR [-v]"

    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print usage
        sys.exit(1)

    src = sys.argv[1]
    tdir = sys.argv[2]

    verbose = False
    if len(sys.argv) == 4:
        if sys.argv[3] == '-v':
            verbose = True
        else:
            print usage
            sys.exit(1)
 
    hk_move( src, tdir, verbose ).execute()

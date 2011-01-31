#!/usr/bin/env python

from hkdiff import diff
from housekeeping import HousekeepingError, NonIdenticalTargetError
import subprocess
from mkdir_p import mkdir_p
import os, sys

class hk_copy:
    """
        Copy source (file or dir) to target if the target does not already exist.
        If target does exist, do nothing, or warn if it is not identical to source.
    """
    def __init__( self, src, tdir, verbose=False ):
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

        print "\nCopy"
        print " + source: ", src
        print " + target: ", self.target

    def execute( self ):
        if os.path.exists( self.target ):
            # target already exists, check if identical
            try:
                diff( self.src, self.target, verbose=self.verbose ).execute()
            except NonIdenticalTargetError, x:
                print 'WARNING: target exists and differs from source!'
            else:
                # target is identical, job done.
                print "(identical target exists already)"
                return

        # target does not exist yet; OK to copy.
        
        # NOTE: shutils.copytree() does not allow the destination
        # directory to exist beforehand; i.e. it won't add files to an
        # existing directory. So for now we'll do it by executing a
        # shell command.
        # subprocess.call() takes a list: [ command, arg1, arg2, ...]
        commandlist = [ 'cp', '-r', self.src, self.tdir ]
        command = ' '.join(commandlist)
        # THIS BLOCKS UNTIL THE COMMAND COMPLETES
        # and raises OSError if the command cannot be invoked.
        retcode = subprocess.call( commandlist )
        if retcode != 0:
            # command failed
            raise OperationFailedError, 'ERROR: Copy failed!'
        else:
            print "Succeeded"
                
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
 
    try:
        hk_copy( src, tdir, verbose ).execute()
    except NonIdenticalTargetError, x:
        print x

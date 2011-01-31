#!/usr/bin/env python

from hkdiff import diff
import os, sys

class hk_move:
    def __init__( self, src, dst=None, debug=False ):
        self.src = src
        self.dst = dst
        self.debug = debug

    def execute( self ):
        if self.dst:
            if not diff( self.src, self.dst, debug=self.debug ).execute(): 
                return False
        # shutil.move() is SAFE, docs say:
        #   Recursively move a file or directory to another location.
        #   If the destination is on the current filesystem, then simply
        #   use rename. Otherwise, copy src (with copy2()) to the dst
        #   and then remove src.
        shutil.move( entrypath, dest )
        return True
                
if __name__ == "__main__":
    usage = "USAGE: " + sys.argv[0] + " SRC DST"
    if len( sys.argv ) != 3:
        print usage
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2]
    if hk_move src, dst, debug=True ).execute():
        print "delete succeeded"
        sys.exit(0)
    else:
        print "delete failed"
        sys.exit(1)

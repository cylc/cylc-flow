#!/usr/bin/env python

from hkdiff import diff
import os, sys

class hk_delete:
    def __init__( self, src, dst=None, debug=False ):
        self.src = src
        self.dst = dst
        self.debug = debug

    def execute( self ):
        if self.dst:
            if not diff( self.src, self.dst, debug=self.debug ).execute(): 
                return False
        if os.path.isdir( self.src ):
            shutil.rmtree( self.src )
        elif os.path.isfile( self.src ):
            os.unlink( self.src )
        return True
                
if __name__ == "__main__":
    usage = "USAGE: " + sys.argv[0] + " SRC DST"
    if len( sys.argv ) != 3:
        print usage
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2]
    if hk_delete( src, dst, debug=True ).execute():
        print "delete succeeded"
        sys.exit(0)
    else:
        print "delete failed"
        sys.exit(1)

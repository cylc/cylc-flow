#!/usr/bin/env python

import sys, os
import subprocess
from housekeeping import NonIdenticalTargetError

class diff:
    """
        Raise a NonIdenticalTarget Error if soure and target (files or
        directories) differ.
    """
    def __init__( self, source, target, verbose=False ):
        # Calling code should confirm source and target exist.
        self.source = source
        self.target = target
        self.verbose = verbose
        self.indent = '   '

        if verbose:
            print self.indent + "Diff:"
            print self.indent + " + source: " + source
            print self.indent + " + target: " + target

    def execute( self ):
        # There seems to be no Pythonic 'diff' ...
        # subprocess.call() takes a list: [ command, arg1, arg2, ...]
        # recursive diff
        command_list = [ 'diff', '-r', self.target, self.source ]
        command = ' '.join( command_list )

        # THIS BLOCKS UNTIL THE COMMAND COMPLETES
        # and raises OSError if the command cannot be invoked.
        retcode = subprocess.call( command_list, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT )
        if retcode != 0:
            raise NonIdenticalTargetError, 'WARNING: source and target differ'
        else:
            if self.verbose:
                print self.indent + "Source and target are identical"

if __name__ == "__main__":

    usage = "USAGE: " + sys.argv[0] + " SRC CHK [-v]"

    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print usage
        sys.exit(1)

    src = sys.argv[1]
    chk = sys.argv[2]

    verbose = False
    if len(sys.argv) == 4:
        if sys.argv[3] == '-v':
            verbose = True
        else:
            print usage
            sys.exit(1)
    
    diff( src, chk, verbose ).execute()

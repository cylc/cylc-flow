#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys, os
import subprocess
from housekeeping import NonIdenticalTargetError
import flags

class diff:
    """
        Difference source and target items (files or directories) and
        raise a NonIdenticalTarget Error if they differ.
        If initialized with 'cheap=True' just compare file sizes.
    """
    def __init__( self, source, target, cheap=False ):
        # Calling code should confirm source and target exist.
        self.source = source
        self.target = target
        self.cheap = cheap
        self.indent = '   '

        if flags.verbose:
            print self.indent + "Diff:"
            print self.indent + " + source: " + source
            print self.indent + " + target: " + target

    def execute( self ):
        if os.path.isfile( self.source ):
            if self.size_differs():
                # size differs => files differ
                if flags.verbose:
                    print self.indent + "Source and target differ in size"
                raise NonIdenticalTargetError, 'WARNING: source and target differ in size'

            else:
                # size same, file may differ
                if flags.verbose:
                    print self.indent + "Source and target are identical in size"
                if self.cheap:
                    # assume files identical if size same
                    return
                else:
                    # same size but caller wants real diff to be sure
                    pass
        else:
            # directories: have to do a real diff
            pass

        self.real_diff()

    def real_diff( self ):
        # There seems to be no Pythonic 'diff' ...
        # subprocess.call() takes a list: [ command, arg1, arg2, ...]
        # recursive diff
        command_list = [ 'diff', '-r', self.target, self.source ]
        command = ' '.join( command_list )

        # THIS BLOCKS UNTIL THE COMMAND COMPLETES
        # and raises OSError if the command cannot be invoked.
        retcode = subprocess.call( command_list, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT )
        if retcode != 0:
            if flags.verbose:
                print self.indent + "Source and target differ"
            raise NonIdenticalTargetError, 'WARNING: source and target differ'
        else:
            if flags.verbose:
                print self.indent + "Source and target are identical"

    def size_differs( self ):
        size_src = os.stat( self.source ).st_size
        size_dst = os.stat( self.target ).st_size
        if size_src != size_dst:
            return True
        else:
            return False

if __name__ == "__main__":

    #cheap = False
    cheap = True

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

    diff( src, chk, verbose, cheap ).execute()

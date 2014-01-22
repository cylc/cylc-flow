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

import sys, re
import subprocess
import flags

# Instead of p.wait() below, We could use p.poll() which returns None
# until process p finishes, after which it returns p's exit status; this
# would allow print out of exactly when each process finishes. Same
# result in the end though, in terms of whole batch wait.

class batchproc:
    """ Batch process items that return a subprocess-style command list
        [command, arg1, arg2, ...] via an execute() method. Items are
        added until a batch fills up, then the whole batch is processed
        in parallel and we wait on the whole batch to complete before
        beginning the next batch.  
        Users should do a final call to process() to handle any final
        items in an incomplete batch."""

    def __init__( self, size=1, shell=False ):
        self.batchno = 0
        self.items = []
        self.size = int(size)
        self.shell = shell
        print
        print "  Initializing parallel batch processing, batch size", size
        print

    def add_or_process( self, item ):
        n_actioned = 0
        self.items.append( item )
        if len( self.items ) >= self.size:
            n_actioned = self.process()
            self.items = []
        return n_actioned

    def process( self ):
        if len( self.items ) == 0:
            return 0
        self.batchno += 1
        if flags.verbose:
            print "  Batch No.", self.batchno
        proc = []
        count = 0
        n_succeeded = 0
        for item in self.items:
            # SPAWN BATCH MEMBER PROCESSES IN PARALLEL
            proc.append( subprocess.Popen( item.execute(), shell=self.shell, \
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE ))
        for p in proc:
            # WAIT FOR ALL PROCESSES TO FINISH
            count += 1
            p.wait()   # blocks until p finishes
            stdout, stderr = p.communicate()
            error_reported = False
            if stderr != '':
                error_reported = True
                print '  ERROR reported in Batch', self.batchno, 'member', count
            if stdout != '':
                if flags.verbose or error_reported:
                    print '    Batch', self.batchno, 'member', count, 'stdout:'
                for line in re.split( r'\n', stdout ):
                    if flags.verbose or error_reported:
                        print '   ', line
                    if re.search( 'SUCCEEDED', line ):
                        n_succeeded += 1
            if error_reported:
                print '    Batch', self.batchno, 'member', count, 'stderr:'
                for line in re.split( r'\n', stderr ):
                    print '   ', line

        return n_succeeded

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
    for i in range(10):
        b.add_or_process( item(i) )
    # process any leftovers
    b.process()


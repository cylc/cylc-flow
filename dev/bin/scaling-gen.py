#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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

"""Generate a suite of M linear chains of N dummy tasks."""

import os, sys
from mkdir_p import mkdir_p
import random

def usage():
    print "USAGE: sys.argv[0] N_TASKS"
    print "(INTEGER number of tasks)"

try:
    M = int(sys.argv[1])
    N = int(sys.argv[2])
except:
    usage()
    sys.exit(1)

try:
    tmpdir = os.environ['TMPDIR']
except:
    print 'ERROR: you must define $TMPDIR'
    sys.exit(1)

name = 'T_' + str(M) + 'x' + str(N)
group = 'scaling'
suite = group + ':' + name

os.system( 'cylc db unregister --obliterate --force ' + suite )

dir = os.path.join( tmpdir, group, name )
mkdir_p( dir )
 
suiterc = os.path.join( dir, 'suite.rc' )

FILE = open( suiterc, 'wb' )

FILE.write( "title = scaling test " + str(M) + 'x' + str(N) + '\n' )
FILE.write( "description = A test suite containing " + str(M*N) + " tasks\n" )
FILE.write( "job submission method = at_now\n" )

FILE.write( """

[dependencies]
    [[0,6,12,18]]
        graph = \"\"\"
""")

for i in range(1,M*N-M,M):
    for j in range(0,M ):
        k = i + j
        print 'T' + str(k) + ' => T' + str(k+M)
        FILE.write( 'T' + str(k) + ' => T' + str(k+M) + '\n')

FILE.write('\n"""')


FILE.write( """

[tasks]
""" )
for i in range(1,M*N):
    FILE.write( "  [[T" + str(i) + "]]\n" )
    FILE.write( "     [[[environment]]]\n" )
    FILE.write( "  CYLC_SIMULATION_SLEEP = " + str( random.randint(1,15) ) + "\n" )

FILE.close()

os.system( 'cylc db register ' + suite + ' ' + dir )


#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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

import sys, subprocess

# subprocess.call() - if shell=True, command is string, not list.

def execute( command_list, ignore_output=False, notify=False ):
    try:
        if ignore_output:
            # THIS BLOCKS UNTIL THE COMMAND COMPLETES
            retcode = subprocess.call( command_list, stdout=open('/dev/null', 'w'), \
                stderr=subprocess.STDOUT )
        else:
            # THIS BLOCKS UNTIL THE COMMAND COMPLETES
            retcode = subprocess.call( command_list )
        if retcode != 0:
            # the command returned non-zero exist status
            print >> sys.stderr, ' '.join( command_list ), ' failed: ', retcode
            sys.exit(1)
        else:
            if notify:
                #print ' '.join( command_list ), ' succeeded'
                print 'DONE'
            sys.exit(0)
    except OSError:
        # the command was not invoked
        print >> sys.stderr, 'ERROR: unable to execute ', ' '.join(command_list)
        sys.exit(1)

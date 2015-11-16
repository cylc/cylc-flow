#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import subprocess

# subprocess.call() - if shell=True, command is string, not list.


def execute(command_list, ignore_output=False, notify=False):
    try:
        if ignore_output:
            # THIS BLOCKS UNTIL THE COMMAND COMPLETES
            retcode = subprocess.call(
                command_list,
                stdout=open('/dev/null', 'w'),
                stderr=subprocess.STDOUT)
        else:
            # THIS BLOCKS UNTIL THE COMMAND COMPLETES
            retcode = subprocess.call(command_list)
        if retcode != 0:
            # the command returned non-zero exist status
            print >> sys.stderr, ' '.join(command_list), ' failed: ', retcode
            sys.exit(1)
        else:
            if notify:
                # print ' '.join(command_list), ' succeeded'
                print 'DONE'
            sys.exit(0)
    except OSError:
        # the command was not invoked
        print >> sys.stderr, (
            'ERROR: unable to execute ', ' '.join(command_list))
        sys.exit(1)

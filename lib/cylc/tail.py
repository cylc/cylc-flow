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

import time

def tail( file ):
    while True:
        where = file.tell()
        line = file.readline()
        if not line:
            time.sleep( 1 )
            file.seek( where )
            yield None  # return even if no new line so the host thread
                        # doesn't hang when the gui exits.
        else:
            yield line

# FOR NORMAL 'tail -F' behaviour:
#def tail( file ):
#    interval = 1.0
#
#    while True:
#        where = file.tell()
#        line = file.readline()
#        if not line:
#            time.sleep( interval )
#            file.seek( where )
#        else:
#            yield line

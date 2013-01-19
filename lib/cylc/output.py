#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

import re

class OutputXError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr( self.msg )

class outputx(object):
    """
Hold and process explicit internal task outputs during suite configuration.
This is for outputs used as outputs, not outputs used as prerequisites. The
latter can have instrinsic (in message) and evaluation ([T-n]) offsets, but 
these only have intrinsic offsets - they are always evaluated at the task's 
own cycle time.
    """
    def __init__(self, msg, cyclr ):
        self.offset = None
        self.cyclr = cyclr
        # Replace CYLC_TASK_CYCLE_TIME with TAG 
        self.msg = msg
        m = re.search( '\[\s*T\s*([+-])\s*(\d+)\s*\]', self.msg )
        if m:
            sign, offset = m.groups()
            if sign != '+':
                raise OutputXError, "ERROR, task output offsets must be positive: " + self.msg
            self.offset = int(offset)

    def get( self, ctime ):
        if self.offset:
            ctime = self.cyclr.offset( ctime, - self.offset )
        return re.sub( '\[\s*T.*?\]', ctime, self.msg )


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

import re
from cycle_time import CycleTimeError, ct

class TaskIDError( Exception ):
    """
    Attributes:
        message - what the problem is. 
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class InvalidTaskIDError( TaskIDError ):
    pass
class InvalidCycleTimeError( TaskIDError ):
    pass

class id( object ):

    """Cylc task IDs for user input: 
            cycling tasks:      NAME%CYCLE   - CYCLE is YYYYMMDDHH[mm[ss]]
            asynchronous tasks: NAME%TAG     - TAG is a:INTEGER
       The 'a:' prefix distinguishes asynchronous tasks on the command line
       and therefore allows commands to check for valid cycle times."""

    def __init__( self, id ):

        self.cycling = False
        self.asynchronous = False

        try:
            self.name, self.tag = id.split( '%' )
        except ValueError:
            raise InvalidTaskIDError, 'Illegal task ID: ' + id
 
        if re.match( '^a:', self.tag ):
            # indicates asynchronous task
            self.tag = self.tag[2:]
            self.asynchronous = True
        else:
            # cycling task
            self.cycling = True
            try:
                cycle = ct(self.tag).get()
            except CycleTimeError, x:
                raise InvalidCycleTimeError, str(x)

        self.id = self.name + '%' + self.tag

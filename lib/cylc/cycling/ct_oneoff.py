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

from cylc.cycling.base import cycler

class ct_oneoff( cycler ):
    @classmethod
    def offset( cls, tag, n ):
        return None

    def __init__( self, ctime ):
        # TODO: HANDLE ALLOWED CTIME FORMATS PROPERLY
        self.ctime = ctime

    def get_min_cycling_interval( self ):
        return None

    def next( self, tag ):
        return None

    def initial_adjust_up( self, tag ):
        return self.ctime

    def valid( self, tag ):
        #return tag == self.ctime
        # TODO - IN TASKDEF.PY THE CYC.VALID TEST PREVENTS USE OF PREQS
        # FOR THESE TASKS IF WE USE TAG == SELF.CTIME HERE.
        return True


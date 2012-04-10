#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

class triggerx(object):
    """
Class to hold and process task triggers during suite configuration.
The information here eventually ends up as task proxy preqrequisites.

Note on trigger time offsets:
    foo[T-n] => bar   # bar triggers off "foo succeeded at T-n"
(a) foo[T-n]:x => bar # bar triggers off "output x of foo evaluated at T-n"
where output x of foo may also have an offset:
(b) x = "foo outputx completed for <CYLC_TASK_CYCLE_TIME[+n]>"

(a) is an "evaluation offset"
(b) is an "intrinsic offset"
    """

    def __init__(self, name ):
        self.name = name
        self.msg = None
        self.intrinsic_offset = None
        self.evaluation_offset = None
        self.type = 'succeeded'
        self.cycling = False
        self.async_oneoff = False
        self.async_repeating = False
        self.asyncid_pattern = None
        self.startup = False
        self.suicide = False
    def set_suicide( self, suicide ):
        self.suicide = suicide
    def set_startup( self ):
        self.startup = True
    def set_async_oneoff( self ):
        self.async_oneoff = True
    def set_async_repeating( self, pattern ):
        self.async_repeating = True
        self.asyncid_pattern = pattern
    def set_cycling( self ):
        self.cycling = True
    def set_special( self, msg ):
        # explicit internal output message ...
        # Replace CYLC_TASK_CYCLE_TIME with TAG in explicit internal output message
        self.msg = re.sub( 'CYLC_TASK_CYCLE_TIME', 'TAG', msg )
        preq = self.msg
        m = re.search( '<TAG\s*\+\s*(\d+)>', preq )
        if m:
            self.intrinsic_offset = m.groups()[0]
    def set_type( self, type ):
        # started, succeeded, failed
        self.type = type
    def set_offset( self, offset ):
        self.evaluation_offset = offset
    def get( self, ctime, cycler ):
        if self.async_oneoff:
            # oneoff async
            preq = self.name + '%1' + ' ' + self.type
        elif self.async_repeating:
            # repeating async
            preq = re.sub( '<ASYNCID>', '(' + self.asyncid_pattern + ')', self.msg )
        else:
            # cycling
            if self.msg:
                # explicit internal output ...
                preq = self.msg
                if self.intrinsic_offset:
                    ctime = cycler.offset( ctime, self.intrinsic_offset,True )
                if self.evaluation_offset:
                    ctime = cycler.offset( ctime, self.evaluation_offset )
                preq = re.sub( '<TAG.*?>', ctime, preq )
            else:
                # implicit output
                if self.evaluation_offset:
                    ctime = cycler.offset( ctime, self.evaluation_offset )
                preq = self.name + '%' + ctime + ' ' + self.type
        return preq


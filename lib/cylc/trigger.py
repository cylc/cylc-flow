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

import cylc.TaskID
from cylc.cycling.loader import interval

import re

class TriggerXError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr( self.msg )

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
        self.type = None
        self.cycling = False
        self.async_repeating = False
        self.asyncid_pattern = None
        self.suicide = False
    def set_suicide( self, suicide ):
        self.suicide = suicide
    def set_async_repeating( self, pattern ):
        self.async_repeating = True
        self.asyncid_pattern = pattern
    def set_cycling( self ):
        self.cycling = True
    def set_special( self, msg ):
        # explicit internal output message ...
        self.msg = msg
        # TODO ISO:
        m = re.search( '\[\s*T\s*([+-])\s*(\d+)\s*\]', msg )
        if m:
            sign, offset = m.groups()
            if sign != '+':
                raise TriggerXError, "ERROR, task output offsets must be positive: " + self.msg
            self.intrinsic_offset = interval( offset )
    def set_type( self, type ):
        if type not in [ 'submitted', 'submit-failed', 'started', 'succeeded', 'failed' ]:
            raise TriggerXError, 'ERROR, ' + self.name + ', illegal trigger type: ' + type
        self.type = type
    def set_offset( self, offset ):
        self.evaluation_offset = interval( offset )
    def get( self, ctime ):
        if self.async_repeating:
            # repeating async
            preq = re.sub( '<ASYNCID>', '(' + self.asyncid_pattern + ')', self.msg )
        else:
            if self.msg:
                # explicit internal output ...
                preq = self.msg
                if self.intrinsic_offset:
                    ctime += self.intrinsic_offset
                if self.evaluation_offset:
                    ctime -= self.evaluation_offset
                preq = re.sub( '\[\s*T\s*.*?\]', str(ctime), preq )
            else:
                # implicit output
                if self.evaluation_offset:
                    ctime -= self.evaluation_offset
                preq = cylc.TaskID.get( self.name, str(ctime) ) + ' ' + self.type
        return preq


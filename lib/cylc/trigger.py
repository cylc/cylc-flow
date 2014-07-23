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
from cylc.cycling.loader import (
    get_interval, get_interval_cls, get_point_relative)

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
(b) x = "foo outputx completed for <CYLC_TASK_CYCLE_POINT[+n]>"

(a) is an "evaluation offset"
(b) is an "intrinsic offset"
    """

    def __init__(self, name ):
        self.name = name
        self.msg = None
        self.intrinsic_offset = None
        self.evaluation_offset_string = None
        self.cycle_point = None
        self.type = None
        self.cycling = False
        self.suicide = False

    def set_suicide( self, suicide ):
        self.suicide = suicide

    def set_cycling( self ):
        self.cycling = True

    def set_special( self, msg, base_interval=None ):
        # explicit internal output message ...
        self.msg = msg
        # TODO ISO: support '+PT6H', etc
        m = re.search( '\[\s*T?\s*([+-]?)\s*(.*)\s*\]', msg )
        if m:
            sign, offset = m.groups()
            if sign and sign != '+':
                raise TriggerXError, "ERROR, task output offsets must be positive: " + self.msg
            if offset:
                self.intrinsic_offset = base_interval.get_inferred_child(
                    offset)
            else:
                self.intrinsic_offset = get_interval_cls().get_null()

    def set_type( self, type ):
        if type not in [ 'submitted', 'submit-failed', 'started', 'succeeded', 'failed' ]:
            raise TriggerXError, 'ERROR, ' + self.name + ', illegal trigger type: ' + type
        self.type = type

    def set_cycle_point( self, cycle_point ):
        self.cycle_point = cycle_point

    def set_offset_string( self, offset_string ):
        self.evaluation_offset_string = offset_string

    def get( self, ctime ):
        """Return a prerequisite string and the relevant point for ctime."""
        if self.msg:
            # explicit internal output ...
            preq = self.msg
            if self.intrinsic_offset:
                ctime += self.intrinsic_offset
            if self.evaluation_offset_string:
                ctime = get_point_relative(
                    self.evaluation_offset_string, ctime)
            if self.cycle_point:
                ctime = self.cycle_point
            preq = re.sub( '\[\s*[T\s*.*?\]', str(ctime), preq )
        else:
            # implicit output
            if self.evaluation_offset_string:
                ctime = get_point_relative(
                    self.evaluation_offset_string, ctime)
            if self.cycle_point:
                ctime = self.cycle_point
            preq = cylc.TaskID.get( self.name, str(ctime) ) + ' ' + self.type
        return preq, ctime

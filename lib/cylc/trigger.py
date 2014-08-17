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

import re

import cylc.TaskID
from cylc.cycling.loader import (
    get_interval, get_interval_cls, get_point_relative)
from cylc.task_state import task_state

class TriggerError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr( self.msg )

class trigger(object):
    """
Task triggers are used to generate task prerequisite messages.

Note on trigger time offsets:
  bar triggers off "foo succeeded at -P1D"
    foo[-P1D] => bar
  bar triggers off "message output x of foo evaluated for -P1D"
    foo[-P1D]:x => bar
Message output x may have an offset too:
[runtime]
   [[foo]]
      [[[outputs]]]
         x = "X uploaded for [P1D]"
         y = "Y uploaded for []"

(a) is an "graph offset"
(b) is an "message offset"
    """

    def __init__(self, name):
        self.name = name
        self.message = None
        self.message_offset = None
        self.graph_offset_string = None
        self.cycle_point = None
        self.standard_type = None
        self.cycling = False
        self.suicide = False

    def set_suicide(self, suicide):
        self.suicide = suicide

    def set_cycling(self):
        self.cycling = True

    def set_standard_trigger(self, qualifier):
        self.standard_type = task_state.get_legal_trigger_state(qualifier)

    def set_message_trigger(self, msg, offset=None):
        self.message = msg
        self.message_offset = offset

    def set_cycle_point(self, cycle_point):
        self.cycle_point = cycle_point

    def set_offset_string(self, offset_string):
        self.graph_offset_string = offset_string

    def get(self, ctime):
        """Return a prerequisite string and the relevant point for ctime."""
        if self.message:
            preq = self.message
            if self.cycle_point:
                ctime = self.cycle_point
            else:
                if self.message_offset:
                    ctime += self.message_offset
                if self.graph_offset_string:
                    ctime = get_point_relative(
                            self.graph_offset_string, ctime)
            preq = re.sub( '\[.*\]', str(ctime), preq )
        elif self.standard_type:
            if self.cycle_point:
                ctime = self.cycle_point
            elif self.graph_offset_string:
                ctime = get_point_relative(
                    self.graph_offset_string, ctime)
            preq = cylc.TaskID.get(self.name, str(ctime)) + ' ' + self.standard_type
        else:
            # TODO
            raise Exception("shite")
        return preq, ctime

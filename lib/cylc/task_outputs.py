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
from cylc.cycling.loader import get_point
from cylc.task_id import TaskID

class TaskOutputs(object):
    _INSTANCE = None

    """Store task output messages for matching task prerequisites.
    
    The internal dict is optimized for dependency matching and deletion, but
    not for cycle point based cleanup: self.messages[message] = taskid.
    """

    @classmethod
    def get_inst(cls):
        """Return a singleton instance of this class."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self):
        self.messages = {}

    def register(self, taskid, message):
        # Assumes task output messages are unique across the suite.
        self.messages[message] = taskid

    def unregister(self, taskid, message):
        try:
            del self.messages[message]
        except KeyError:
            pass

    def get_taskid(self, message):
        return self.messages.get(message, None)

    def cleanup(self, min_point):
        cleaned_up = {}
        for message, taskid in self.messages.items():
            name, point_string = TaskID.split(taskid)
            point = get_point(point_string)
            if point < min_point:
                # TODO - housekeep the db task_outputs table
                cleaned_up[message] = taskid
                del self.messages[message]
        #if cleaned_up:
        #    print '\nCleanded up:'
        #    for taskid in cleaned_up.keys():
        #        print ' ', taskid
        #    sys.stdout.flush()
        #self.task_outputs.dump()

        return cleaned_up

    def dump(self):
        print '\nRegistered outputs:'
        for message, taskid in self.messages.items():
            print ' ', taskid, message
        sys.stdout.flush()

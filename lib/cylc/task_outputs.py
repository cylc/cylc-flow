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
import cylc.rundb
from cylc.cycling.loader import get_point
from cylc.task_id import TaskID

class TaskOutputs(object):
    """Store task output messages for matching task prerequisites.
    
    The internal dict is indexed by messaage for easy dependency matching and
    deletion, but not for cycle point based cleanup.

    Task output messages are assumed to be unique across the suite.
    """

    _INSTANCE = None

    @classmethod
    def get_inst(cls):
        """Return a singleton instance of this class."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self):
        # All messages.
        self.messages = {}
        self.db_queue = []

    def register(self, taskid, message):
        self.messages[message] = taskid
        self.db_queue_record(taskid, message)

    def unregister(self, taskid, message):
        try:
            del self.messages[message]
        except KeyError as exc:
            # No such message.
            # TODO - flag an error here?
            pass
        else:
            self.db_queue_delete(taskid, message)

    def get_taskid(self, message):
        return self.messages.get(message, None)

    def cleanup(self, min_point):
        """Removed expired messages."""

        # TODO - this does a string-to-point conversion and comparison for
        # every task, in every cleanup ... can it be made more efficient?
        # (are the conversions and comparisons memoized?)
        for message, taskid in self.messages.items():
            name, point_string = TaskID.split(taskid)
            point = get_point(point_string)
            if point < min_point:
                # TODO - housekeep the db task_outputs table
                self.unregister(taskid, message)

    def dump(self):
        print '\nRegistered outputs:'
        for message, taskid in self.messages.items():
            print ' ', taskid, message
        sys.stdout.flush()

    def db_queue_record(self, taskid, message):
        """Record a task output to the run DB."""
        #if self.validate_mode:
        #    # Don't touch the db during validation.
        #    return
        self.db_queue.append(cylc.rundb.RecordOutputObject(
            taskid, message))

    def db_queue_delete(self, taskid, message):
        """Record a task output to the run DB."""
        #if self.validate_mode:
        #    # Don't touch the db during validation.
        #    return
        self.db_queue.append(cylc.rundb.DeleteOutputObject(
            taskid, message))

    def get_db_ops(self):
        ops = self.db_queue
        self.db_queue = []
        return ops

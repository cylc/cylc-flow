#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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

"""Task output messages and associated logic."""


import sys

# Standard task output strings, used for triggering.
TASK_OUTPUT_EXPIRED = "expired"
TASK_OUTPUT_SUBMITTED = "submitted"
TASK_OUTPUT_SUBMIT_FAILED = "submit-failed"
TASK_OUTPUT_STARTED = "started"
TASK_OUTPUT_SUCCEEDED = "succeeded"
TASK_OUTPUT_FAILED = "failed"


class TaskOutputs(object):

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["owner_id", "completed", "not_completed"]

    def __init__(self, owner_id):

        self.owner_id = owner_id
        # Store completed and not-completed outputs in separate
        # dicts to allow quick passing of completed to the broker.

        # Using rhs of dict as a cheap way to get owner ID to receiving
        # tasks via the dependency broker object:
        # self.(not)completed[message] = owner_id

        self.completed = {}
        self.not_completed = {}

    def count(self):
        return len(self.completed) + len(self.not_completed)

    def count_completed(self):
        return len(self.completed)

    def dump(self):
        # return a list of strings representing each message and its state
        res = []
        for key in self.not_completed:
            res.append([key, False])
        for key in self.completed:
            res.append([key, True])
        return res

    def all_completed(self):
        return len(self.not_completed) == 0

    def is_completed(self, msg):
        return self._qualify(msg) in self.completed

    def _qualify(self, msg):
        # Prefix a message string with task ID.
        return "%s %s" % (self.owner_id, msg)

    def set_completed(self, msg):
        message = self._qualify(msg)
        try:
            del self.not_completed[message]
        except:
            pass
        self.completed[message] = self.owner_id

    def exists(self, msg):
        message = self._qualify(msg)
        return message in self.completed or message in self.not_completed

    def set_all_incomplete(self):
        for message in self.completed.keys():
            del self.completed[message]
            self.not_completed[message] = self.owner_id

    def set_all_completed(self):
        for message in self.not_completed.keys():
            del self.not_completed[message]
            self.completed[message] = self.owner_id

    def add(self, msg, completed=False):
        # Add a new output message, prepend my task ID.
        message = self._qualify(msg)
        if message in self.completed or message in self.not_completed:
            # duplicate output messages are an error.
            print >> sys.stderr, (
                'WARNING: output already registered: ' + message)
        if not completed:
            self.not_completed[message] = self.owner_id
        else:
            self.completed[message] = self.owner_id

    def remove(self, msg):
        """Remove an output, if it exists."""
        message = self._qualify(msg)
        try:
            del self.completed[message]
        except:
            try:
                del self.not_completed[message]
            except:
                pass

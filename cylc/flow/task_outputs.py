#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Task output message manager and constants."""


# Standard task output strings, used for triggering.
TASK_OUTPUT_EXPIRED = "expired"
TASK_OUTPUT_SUBMITTED = "submitted"
TASK_OUTPUT_SUBMIT_FAILED = "submit-failed"
TASK_OUTPUT_STARTED = "started"
TASK_OUTPUT_SUCCEEDED = "succeeded"
TASK_OUTPUT_FAILED = "failed"

_SORT_ORDERS = (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED)

_TRIGGER = 0
_MESSAGE = 1
_IS_COMPLETED = 2


class TaskOutputs(object):
    """Task output message manager.

    Manage standard task outputs and custom outputs, e.g.:
    [scheduling]
        [[dependencies]]
            graph = t1:trigger1 => t2
    [runtime]
        [[t1]]
            [[[outputs]]]
                trigger1 = message 1

    Can search item by message string or by trigger string.
    """

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["_by_message", "_by_trigger"]

    def __init__(self, tdef):
        self._by_message = {}
        self._by_trigger = {}
        # Add standard outputs.
        for output in _SORT_ORDERS:
            self.add(output)
        # Add custom message outputs.
        for trigger, message in tdef.outputs:
            self.add(message, trigger)

    def add(self, message, trigger=None, is_completed=False):
        """Add a new output message"""
        if trigger is None:
            trigger = message
        self._by_message[message] = [trigger, message, is_completed]
        self._by_trigger[trigger] = self._by_message[message]

    def all_completed(self):
        """Return True if all all outputs completed."""
        return all(val[_IS_COMPLETED] for val in self._by_message.values())

    def exists(self, message=None, trigger=None):
        """Return True if message/trigger is identified as an output."""
        try:
            return self._get_item(message, trigger) is not None
        except KeyError:
            return False

    def get_all(self):
        """Return an iterator for all outputs."""
        return sorted(self._by_message.values(), key=self.msg_sort_key)

    def get_completed(self):
        """Return all completed output messages."""
        ret = []
        for value in self.get_all():
            if value[_IS_COMPLETED]:
                ret.append(value[_MESSAGE])
        return ret

    def get_completed_customs(self):
        """Return all completed custom outputs.

        Return a list in this form: [(trigger1, message1), ...]
        """
        ret = []
        for value in self.get_all():
            if value[_IS_COMPLETED] and value[_TRIGGER] not in _SORT_ORDERS:
                ret.append((value[_TRIGGER], value[_MESSAGE]))
        return ret

    def has_custom_triggers(self):
        """Return True if it has any custom triggers."""
        return any(key not in _SORT_ORDERS for key in self._by_trigger)

    def get_not_completed(self):
        """Return all not-completed output messages."""
        ret = []
        for value in self.get_all():
            if not value[_IS_COMPLETED]:
                ret.append(value[_MESSAGE])
        return ret

    def is_completed(self, message=None, trigger=None):
        """Return True if output of message is completed."""
        try:
            return self._get_item(message, trigger)[_IS_COMPLETED]
        except KeyError:
            return False

    def remove(self, message=None, trigger=None):
        """Remove an output by message, if it exists."""
        try:
            trigger, message = self._get_item(message, trigger)[:2]
        except KeyError:
            pass
        else:
            del self._by_message[message]
            del self._by_trigger[trigger]

    def set_all_completed(self):
        """Set all outputs to complete."""
        for value in self._by_message.values():
            value[_IS_COMPLETED] = True

    def set_all_incomplete(self):
        """Set all outputs to incomplete."""
        for value in self._by_message.values():
            value[_IS_COMPLETED] = False

    def set_completion(self, message, is_completed):
        """Set output message completion status to is_completed (bool)."""
        if message in self._by_message:
            self._by_message[message][_IS_COMPLETED] = is_completed

    def set_msg_trg_completion(self, message=None, trigger=None,
                               is_completed=True):
        """Set the output identified by message/trigger to is_completed.

        Return:
            - Value of trigger (True) if completion flag is changed,
            - False if completion is unchanged, or
            - None if message/trigger is not found.

        """
        try:
            item = self._get_item(message, trigger)
            old_is_completed = item[_IS_COMPLETED]
            item[_IS_COMPLETED] = is_completed
        except KeyError:
            return None
        else:
            if bool(old_is_completed) == bool(is_completed):
                return False
            else:
                return item[_TRIGGER]

    def _get_item(self, message, trigger):
        """Return self._by_trigger[trigger] or self._by_message[message].

        whichever is relevant.
        """
        if message is None:
            return self._by_trigger[trigger]
        else:
            return self._by_message[message]

    @staticmethod
    def msg_sort_key(item):
        """Compare by _MESSAGE."""
        try:
            ind = _SORT_ORDERS.index(item[_MESSAGE])
        except ValueError:
            ind = 999
        return (ind, item[_MESSAGE] or '')

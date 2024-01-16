# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

from typing import List

# Standard task output strings, used for triggering.
TASK_OUTPUT_EXPIRED = "expired"
TASK_OUTPUT_SUBMITTED = "submitted"
TASK_OUTPUT_SUBMIT_FAILED = "submit-failed"
TASK_OUTPUT_STARTED = "started"
TASK_OUTPUT_SUCCEEDED = "succeeded"
TASK_OUTPUT_FAILED = "failed"
TASK_OUTPUT_FINISHED = "finished"

SORT_ORDERS = (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED)

TASK_OUTPUTS = (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_FINISHED,
)

_TRIGGER = 0
_MESSAGE = 1
_IS_COMPLETED = 2


class TaskOutputs:
    """Task output message manager.

    Manage standard task outputs and custom outputs, e.g.:
    [scheduling]
        [[graph]]
            R1 = t1:trigger1 => t2
    [runtime]
        [[t1]]
            [[[outputs]]]
                trigger1 = message 1

    Can search item by message string or by trigger string.
    """

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["_by_message", "_by_trigger", "_required"]

    def __init__(self, tdef):
        self._by_message = {}
        self._by_trigger = {}
        self._required = {}  # trigger: message

        # Add outputs from task def.
        for trigger, (message, required) in tdef.outputs.items():
            self._add(message, trigger, required=required)

        # Handle implicit submit requirement
        if (
            # "submitted" is not declared as optional/required
            tdef.outputs[TASK_OUTPUT_SUBMITTED][1] is None
            # and "submit-failed" is not declared as optional/required
            and tdef.outputs[TASK_OUTPUT_SUBMIT_FAILED][1] is None
        ):
            self._add(
                TASK_OUTPUT_SUBMITTED,
                TASK_OUTPUT_SUBMITTED,
                required=True,
            )

    def _add(self, message, trigger, is_completed=False, required=False):
        """Add a new output message"""
        self._by_message[message] = [trigger, message, is_completed]
        self._by_trigger[trigger] = self._by_message[message]
        if required:
            self._required[trigger] = message

    def set_completed_by_msg(self, message):
        """For flow trigger --wait: set completed outputs from the DB."""
        for trig, msg, _ in self._by_trigger.values():
            if message == msg:
                self._add(message, trig, True, trig in self._required)
                break

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
        """Return an iterator for all output messages."""
        return sorted(self._by_message.values(), key=self.msg_sort_key)

    def get_msg(self, out):
        """Translate a message or label into message, or None if not valid."""
        if out in self._by_message:
            # It's already a valid message.
            return out
        elif out in self._by_trigger:
            # It's a valid trigger label, return the message.
            return (self._by_trigger[out])[1]
        else:
            # Not a valid message or trigger label.
            return None

    def get_completed(self):
        """Return all completed output messages."""
        ret = []
        for value in self.get_all():
            if value[_IS_COMPLETED]:
                ret.append(value[_MESSAGE])
        return ret

    def get_completed_all(self):
        """Return all completed outputs.

        Return a list in this form: [(trigger1, message1), ...]
        """
        ret = []
        for value in self.get_all():
            if value[_IS_COMPLETED]:
                ret.append((value[_TRIGGER], value[_MESSAGE]))
        return ret

    def has_custom_triggers(self):
        """Return True if it has any custom triggers."""
        return any(key not in SORT_ORDERS for key in self._by_trigger)

    def _get_custom_triggers(self, required: bool = False) -> List[str]:
        """Return list of all, or required, custom trigger messages."""
        custom = [
            out[1] for trg, out in self._by_trigger.items()
            if trg not in SORT_ORDERS
        ]
        if required:
            custom = [out for out in custom if out in self._required.values()]
        return custom

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

    def is_incomplete(self):
        """Return True if any required outputs are not complete."""
        return any(
            not completed
            and trigger in self._required
            for trigger, (_, _, completed) in self._by_trigger.items()
        )

    def get_incomplete(self):
        """Return a list of required outputs that are not complete.

        A task is incomplete if:

        * it finished executing without completing all required outputs
        * or if job submission failed and the :submit output was not optional

        https://github.com/cylc/cylc-admin/blob/master/docs/proposal-new-output-syntax.md#output-syntax

        """
        return [
            trigger
            for trigger, (_, _, is_completed) in self._by_trigger.items()
            if not is_completed and trigger in self._required
        ]

    def get_item(self, message):
        """Return output item by message.

        Args:
            message (str): Output message.

        Returns:
            item (tuple):
                label (str), message (str), satisfied (bool)

        """
        if message in self._by_message:
            return self._by_message[message]

    def _get_item(self, message, trigger):
        """Return self._by_trigger[trigger] or self._by_message[message].

        whichever is relevant.
        """
        if message is None:
            return self._by_trigger[trigger]
        else:
            return self._by_message[message]

    def get_incomplete_implied(self, output: str, forced=False) -> List[str]:
        """Return an ordered list of incomplete implied outputs.

        Use to determined implied outputs to complete automatically.

        For forced completion of outputs via `cylc set":
           - complete all implied outputs automatically
           - forced success implies all required outputs
           - (forced failure does not)

        For natural completion of outputs via task messages:
           - complete implied submitted and started outputs automatically
               (runtime outputs cannot be generated without starting the job,
               so missing these only implies e.g. network issues)
           - do not complete other implied outputs automatically (doing so
               would break error detection based on required outputs)

        Note that submitted and started are *implied* by later outputs, but
        submitted is not necessarily *required*.

        """
        implied: List[str] = []

        if forced and output in [TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED]:
            # Finished, so it must have submitted and started.
            implied = [TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED]
            if output == TASK_OUTPUT_SUCCEEDED:
                # Even if success is optional we can assume required custom
                # outputs are on the success path (not so for failure - that
                # depends on when failure occurs during job execution).
                implied += self._get_custom_triggers(required=True)

        elif output == TASK_OUTPUT_STARTED:
            # It must have submitted.
            implied = [TASK_OUTPUT_SUBMITTED]

        elif (
            output in self._get_custom_triggers() or
            output in [TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED]
        ):
            # It must have submitted and started
            implied = [TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED]

        else:
            pass

        return [out for out in implied if not self.is_completed(out)]

    @staticmethod
    def is_valid_std_name(name):
        """Check name is a valid standard output name."""
        return name in SORT_ORDERS

    @staticmethod
    def msg_sort_key(item):
        """Compare by _MESSAGE."""
        try:
            ind = SORT_ORDERS.index(item[_MESSAGE])
        except ValueError:
            ind = 999
        return (ind, item[_MESSAGE] or '')

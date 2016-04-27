#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

import re
import sys

from cylc.task_id import TaskID
from cylc.cycling.loader import (
    get_interval, get_interval_cls, get_point_relative)
from cylc.task_state import TaskState, TaskStateError


warned = False
BCOMPAT_MSG_RE_C5 = re.compile('^(.*)\[\s*T\s*(([+-])\s*(\d+))?\s*\](.*)$')
BCOMPAT_MSG_RE_C6 = re.compile('^(.*)\[\s*(([+-])?\s*(.*))?\s*\](.*)$')
DEPRECN_WARN_TMPL = "WARNING: message trigger offsets are deprecated\n  %s"


def get_message_offset(msg, base_interval=None):
    """Return deprecated message offset, or None.

    TODO - this function can be deleted once the deprecated cycle point offset
    placeholders are removed from cylc (see GitHub #1761).

    """

    offset = None
    global warned

    # cylc-5 [T+n] message offset - DEPRECATED
    m = BCOMPAT_MSG_RE_C5.match(msg)
    if m:
        if not warned:
            print >> sys.stderr, DEPRECN_WARN_TMPL % msg
            warned = True
        prefix, signed_offset, sign, offset, suffix = m.groups()
        if signed_offset is not None:
            offset = base_interval.get_inferred_child(
                signed_offset)
    else:
        # cylc-6 [<interval>] message offset - DEPRECATED
        n = BCOMPAT_MSG_RE_C6.match(msg)
        if n:
            if not warned:
                print >> sys.stderr, DEPRECN_WARN_TMPL % msg
                warned = True
            prefix, signed_offset, sign, offset, suffix = n.groups()
            if offset:
                offset = get_interval(signed_offset)
            else:
                offset = get_interval_cls().get_null()
        # else: Plain message, no offset.
    return offset


class TriggerError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class TaskTrigger(object):
    """
A task trigger is a prerequisite in the abstract, defined by the suite graph.

It generates a concrete prerequisite string given a task's cycle point value.
    """

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["task_name", "suicide", "graph_offset_string", "cycle_point",
                 "message", "message_offset", "builtin"]

    def __init__(
            self, task_name, qualifier=None, graph_offset_string=None,
            cycle_point=None, suicide=False, outputs={}, base_interval=None):

        self.task_name = task_name
        self.suicide = suicide
        self.graph_offset_string = graph_offset_string
        self.cycle_point = cycle_point

        self.message = None
        self.message_offset = None
        self.builtin = None
        qualifier = qualifier or "succeeded"

        # Built-in trigger?
        try:
            self.builtin = TaskState.get_legal_trigger_state(qualifier)
        except TaskStateError:
            pass
        else:
            return

        # Message trigger?
        try:
            self.message = outputs[qualifier]
        except KeyError:
            raise TriggerError(
                "ERROR: undefined trigger qualifier: %s:%s" % (
                    task_name, qualifier))
        else:
            self.message_offset = get_message_offset(self.message,
                                                     base_interval)

    def get_prereq(self, point):
        """Return a prerequisite string."""
        if self.message:
            # Message trigger
            preq = self.message
            msg_point = point
            if self.cycle_point:
                point = self.cycle_point
                msg_point = self.cycle_point
            else:
                if self.message_offset:
                    msg_point = point + self.message_offset
                if self.graph_offset_string:
                    msg_point = get_point_relative(
                        self.graph_offset_string, msg_point)
                    point = get_point_relative(self.graph_offset_string, point)
            preq = "%s %s" % (
                TaskID.get(self.task_name, point),
                re.sub('\[.*\]', str(msg_point), preq))
        else:
            # Built-in trigger
            if self.cycle_point:
                point = self.cycle_point
            elif self.graph_offset_string:
                point = get_point_relative(
                    self.graph_offset_string, point)
            preq = TaskID.get(self.task_name, point) + ' ' + self.builtin
        return preq

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

"""Task definition."""

from cylc.cycling.loader import get_point_relative, get_interval, get_point
from cylc.task_id import TaskID


class TaskDefError(Exception):
    """Exception raise for errors in TaskDef initialization."""

    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.msg = msg

    def __str__(self):
        return "ERROR: %s" % self.msg 


class TaskDef(object):
    """Task definition."""

    def __init__(self, name, rtcfg, run_mode, start_point):
        if not TaskID.is_valid_name(name):
            raise TaskDefError("Illegal task name: %s" % name)

        self.run_mode = run_mode
        self.rtconfig = rtcfg
        self.start_point = start_point

        self.sequences = []
        self.implicit_sequences = []  # Implicit sequences are deprecated.
        self.used_in_offset_trigger = False

        # some defaults
        self.max_future_prereq_offset = None
        self.sequential = False
        self.is_coldstart = False
        self.suite_polling_cfg = {}

        self.clocktrigger_offset = None
        self.namespace_hierarchy = []
        self.triggers = {}
        # message outputs
        self.outputs = []

        self.name = name
        self.elapsed_times = []
        self.mean_total_elapsed_time = None

    def add_trigger(self, triggers, expression, sequence):
        """Add conditional trigger to a named sequence."""
        if sequence not in self.triggers:
            self.triggers[sequence] = []
        self.triggers[sequence].append([triggers, expression])

    def add_sequence(self, sequence, is_implicit=False):
        """Add a sequence."""
        if sequence not in self.sequences:
            self.sequences.append(sequence)
            if is_implicit:
                self.implicit_sequences.append(sequence)

    def describe(self):
        """Return title and description of the current task."""
        info = {}
        for item in 'title', 'description':
            info[item] = self.rtconfig[item]
        return info

    def check_for_explicit_cycling(self):
        """Check for explicitly somewhere.

        Must be called after all graph sequences added.
        """
        if len(self.sequences) == 0 and self.used_in_offset_trigger:
            raise TaskDefError("No cycling sequences defined for %s" % self.name)

    def update_mean_total_elapsed_time(self, t_started, t_succeeded):
        """Update the mean total elapsed time (all instances of this task)."""
        if not t_started:
            # In case the started messaged did not come in.
            # (TODO - and we don't retain started time on restart?)
            return
        self.elapsed_times.append(t_succeeded - t_started)
        self.mean_total_elapsed_time = (
            sum(self.elapsed_times) / len(self.elapsed_times))

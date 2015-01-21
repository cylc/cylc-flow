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
"""Timer for polling task job submission and execution."""

import time
from copy import copy
from collections import deque
from logging import WARNING, INFO

from cylc.cfgspec.globalcfg import GLOBAL_CFG


class PollTimer(object):
    """Timer for polling task job submission and execution."""

    def __init__(self, intervals, defaults, name, log):
        self.intervals = copy(deque(intervals))
        self.default_intervals = deque(defaults)
        self.name = name
        self.log = log
        self.current_interval = None
        self.timeout = None

    def set_host(self, host, set_timer=False):
        """Set the task host.

        The polling comms method is host-specific.

        """
        if GLOBAL_CFG.get_host_item(
                'task communication method', host) == "poll":
            if not self.intervals:
                self.intervals = copy(self.default_intervals)
                self.log(
                    WARNING,
                    '(polling comms) using default %s polling intervals' %
                    self.name
                )
            if set_timer:
                self.set_timer()

    def set_timer(self):
        """Set the timer."""
        try:
            self.current_interval = self.intervals.popleft()  # seconds
        except IndexError:
            # no more intervals, keep the last one
            pass

        if self.current_interval:
            self.log(INFO, 'setting %s poll timer for %d seconds' % (
                self.name, self.current_interval))
            self.timeout = time.time() + self.current_interval
        else:
            self.timeout = None

    def get(self):
        """Return True if it is ready for the next poll."""
        return self.timeout and time.time() > self.timeout

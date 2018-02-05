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

"""Timer for task actions."""

from time import time

from cylc.wallclock import (
    get_seconds_as_interval_string, get_time_string_from_unix_time)


class TaskActionTimer(object):
    """A timer with delays for task actions."""

    # Memory optimization - constrain possible attributes to this list.
    __slots__ = ["ctx", "delays", "num", "delay", "timeout", "is_waiting"]

    def __init__(self, ctx=None, delays=None, num=0, delay=None, timeout=None):
        self.ctx = ctx
        self.delays = None
        self.set_delays(delays)
        self.num = int(num)
        if delay is not None:
            delay = float(delay)
        self.delay = delay
        if timeout is not None:
            timeout = float(timeout)
        self.timeout = timeout
        self.is_waiting = False

    def delay_as_duration(self, offset=0):
        """Return the delay as ISO8601 duration."""
        return get_seconds_as_interval_string(self.delay + offset)

    def is_delay_done(self, now=None):
        """Is timeout done?"""
        if self.timeout is None:
            return False
        if now is None:
            now = time()
        return now > self.timeout

    def is_timeout_set(self):
        """Return True if timeout is set."""
        return self.timeout is not None

    def next(self, no_exhaust=False):
        """Return the next retry delay.

        When delay list has no more item:
        * Return None if no_exhaust is False
        * Return the final delay if no_exhaust is True.
        """
        try:
            self.delay = self.delays[self.num]
        except IndexError:
            if not no_exhaust:
                self.delay = None
        if self.delay is not None:
            self.timeout = time() + self.delay
            self.num += 1
        return self.delay

    def reset(self):
        """Reset num, delay, timeout and is_waiting."""
        self.num = 0
        self.delay = None
        self.timeout = None
        self.is_waiting = False

    def set_delays(self, delays=None):
        """Set delays, ensuring that the values are floats."""
        if delays is None:
            self.delays = [float(0)]
        else:
            self.delays = [float(delay) for delay in delays]

    def set_waiting(self):
        """Set waiting flag, while waiting for action to complete."""
        self.delay = None
        self.is_waiting = True
        self.timeout = None

    def unset_waiting(self):
        """Unset waiting flag after an action has completed."""
        self.is_waiting = False

    def timeout_as_str(self, offset=0):
        """Return the timeout as an ISO8601 date-time string."""
        return get_time_string_from_unix_time(self.timeout + offset)

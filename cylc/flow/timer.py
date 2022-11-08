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

"""Simple timer class."""

from time import time as now
from cylc.flow import LOG
from cylc.flow.wallclock import (
    get_seconds_as_interval_string as get_interval_str
)

from typing import Callable, Optional


class Timer:
    """Simple timer class for workflow timers.

    Examples:
        >>> from time import sleep

        # Patch LOG.warning to capture warning messages
        >>> warnings = []
        >>> orig_log_warning = LOG.warning
        >>> LOG.warning = lambda msg: warnings.append(msg)

        >>> timer = Timer("bob timeout", 1.0)

        # timer attributes
        >>> timer.name
        'bob timer'
        >>> timer.interval
        'PT1S'

        # start timer
        >>> timer.reset()
        >>> warnings[-1]
        'PT1S bob timer starts NOW'

        # check timeout
        >>> sleep(2)
        >>> timer.timed_out()
        True
        >>> warnings[-1]
        'bob timer timed out after PT1S'

        # stop should do nothing after timeou
        >>> warnings = []
        >>> timer.stop()
        >>> warnings
        []

        # start timer again, then stop it
        >>> timer.reset()
        >>> warnings[-1]
        'PT1S bob timer starts NOW'
        >>> timer.stop()
        >>> warnings[-1]
        'bob timer stopped'

        # another stop should do nothing
        >>> warnings = []
        >>> timer.stop()
        >>> warnings
        []

        # Un-patch LOG.warning to avoid breaking subsequent unit tests!
        >>> LOG.warning = orig_log_warning
    """

    def __init__(
        self, name: str, interval: float,
        log_reset_func: Optional[Callable] = None
    ) -> None:
        """Initialize a timer."""
        if log_reset_func is not None:
            self.log_timer_reset = log_reset_func
        else:
            self.log_timer_reset = LOG.warning
        self.name = name.replace('timeout', 'timer')
        self.interval = get_interval_str(interval)
        self.interval_float = interval
        self.timeout: Optional[float] = None

    def reset(self) -> None:
        """Start the timer now (by setting a concrete timeout value)."""
        self.timeout = now() + self.interval_float
        self.log_timer_reset(f"{self.interval} {self.name} starts NOW")

    def stop(self) -> None:
        """Stop the timer."""
        if self.timeout is None:
            return
        self.timeout = None
        LOG.warning(f"{self.name} stopped")

    def timed_out(self) -> bool:
        """Return whether timed out yet."""
        if self.timeout is not None and now() > self.timeout:
            LOG.warning(f"{self.name} timed out after {self.interval}")
            self.timeout = None
            return True
        else:
            return False

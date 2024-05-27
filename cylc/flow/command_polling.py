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
"""Encapsulates polling activity for CLI commands."""

import sys
from time import sleep


class Poller:
    """Encapsulates polling activity for cylc commands. Derived classes
    must override the check() method to test the polling condition."""

    @classmethod
    def add_to_cmd_options(cls, parser, d_interval=60, d_max_polls=10):
        """Add command line options for commands that can do polling."""
        parser.add_option(
            "--max-polls",
            help=r"Maximum number of polls (default: %default).",
            type="int",
            metavar="INT",
            action="store",
            dest="max_polls",
            default=d_max_polls
        )
        parser.add_option(
            "--interval",
            help=r"Polling interval in seconds (default: %default).",
            type="int",
            metavar="SECS",
            action="store",
            dest="interval",
            default=d_interval
        )

    def __init__(self, condition, interval, max_polls, args):
        self.condition = condition  # e.g. "workflow stopped"
        self.interval = interval
        self.max_polls = max_polls or 1  # no point in zero polls
        self.args = args  # any extra parameters needed by check()
        self.n_polls = 0

    async def check(self):
        """Abstract method. Test polling condition."""
        raise NotImplementedError()

    async def poll(self):
        """Poll for the condition embodied by self.check().

        Return True if condition met, or False if polling exhausted.

        """
        while self.n_polls < self.max_polls:
            if self.n_polls > 1:
                sys.stderr.write(".")
                sys.stderr.flush()
            self.n_polls += 1
            if await self.check():
                return True
            if self.max_polls > 1:
                sleep(self.interval)

        sys.stderr.write("\n")
        sys.stderr.flush()
        err = "ERROR: condition not satisfied"
        if self.max_polls > 1:
            err += f" after {self.max_polls} polls"
        sys.stderr.write(err)
        return False

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
"""Encapsulates polling activity for CLI commands."""

import sys
from time import sleep


class Poller(object):
    """Encapsulates polling activity for cylc commands. Derived classes
    must override the check() method to test the polling condition."""

    @classmethod
    def add_to_cmd_options(cls, parser, d_interval=60, d_max_polls=10):
        """Add command line options for commands that can do polling"""
        parser.add_option(
            "--max-polls",
            help="Maximum number of polls (default " + str(d_max_polls) + ").",
            metavar="INT",
            action="store",
            dest="max_polls",
            default=d_max_polls)
        parser.add_option(
            "--interval",
            help=(
                "Polling interval in seconds (default " + str(d_interval) +
                ")."
            ),
            metavar="SECS",
            action="store",
            dest="interval",
            default=d_interval)

    def __init__(self, condition, interval, max_polls, args):

        self.condition = condition  # e.g. "suite stopped"

        # check max_polls is an int
        try:
            self.max_polls = int(max_polls)
        except ValueError:
            sys.exit("max_polls must be an int")

        # check interval is an int
        try:
            self.interval = int(interval)
        except ValueError:
            sys.exit("interval must be an integer")

        self.n_polls = 0
        self.args = args  # any extra parameters needed by check()

    def check(self):
        """Abstract method. Test polling condition."""
        raise NotImplementedError()

    def poll(self):
        """Poll for the condition embodied by self.check().
        Return True if condition met, or False if polling exhausted."""

        if self.max_polls == 0:
            # exit 1 as we can't know if the condition is satisfied
            sys.exit("WARNING: nothing to do (--max-polls=0)")
        elif self.max_polls == 1:
            sys.stdout.write("checking for '%s'" % self.condition)
        else:
            sys.stdout.write("polling for '%s'" % self.condition)

        while self.n_polls < self.max_polls:
            self.n_polls += 1
            if self.check():
                sys.stdout.write(": satisfied\n")
                return True
            if self.max_polls > 1:
                sys.stdout.write(".")
                sleep(self.interval)
        sys.stdout.write("\n")
        if self.max_polls > 1:
            sys.stderr.write(
                "ERROR: condition not satisfied after %d polls\n" %
                self.max_polls)
        else:
            sys.stderr.write("ERROR: condition not satisfied\n")
        return False

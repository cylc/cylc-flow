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
"""Cylc memory and performance profiling."""

import os
import cProfile
import io
import pstats
from subprocess import Popen, PIPE


class Profiler(object):
    """Wrap cProfile, pstats, and memory logging, for performance profiling."""

    def __init__(self, enabled=False):
        """Initialize cProfile."""
        self.enabled = enabled
        if enabled:
            self.prof = cProfile.Profile()
        else:
            self.prof = None

    def start(self):
        """Start profiling."""
        if not self.enabled:
            return
        self.prof.enable()

    def stop(self):
        """Stop profiling and print stats."""
        if not self.enabled:
            return
        self.prof.disable()
        string_stream = io.StringIO()
        stats = pstats.Stats(self.prof, stream=string_stream)
        stats.sort_stats('cumulative')
        stats.print_stats()
        print(string_stream.getvalue())

    def log_memory(self, message):
        """Print a message to standard out with the current memory usage."""
        if not self.enabled:
            return
        proc = Popen(
            ["ps", "h", "-orss", str(os.getpid())],
            stdin=open(os.devnull), stdout=PIPE)
        memory = int(proc.communicate()[0])
        print("PROFILE: Memory: %d KiB: %s" % (memory, message))

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
"""Cylc memory and performance profiling."""

import os
import cProfile
import io
from pathlib import Path
import pstats

import psutil


class Profiler:
    """Wrap cProfile, pstats, and memory logging, for performance profiling."""

    def __init__(self, schd, enabled=False):
        """Initialize cProfile."""
        self.schd = schd
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
        # dump to stdout
        print(string_stream.getvalue())
        # write data file to workflow log dir
        if not self.schd:
            # if no scheduler present (e.g. validate) dump to PWD
            loc = Path()
        else:
            loc = Path(self.schd.workflow_log_dir)
        self.prof.dump_stats(
            Path(loc, 'profile.prof')
        )

    def log_memory(self, message):
        """Print a message to standard out with the current memory usage."""
        if not self.enabled:
            return
        memory = psutil.Process(os.getpid()).memory_info().rss / 1024
        print("PROFILE: Memory: %d KiB: %s" % (memory, message))

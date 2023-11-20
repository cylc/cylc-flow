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

"""Utility for preventing pipes from getting clogged up.

If you're reading files from Popen (i.e. to extract command output) where the
command output has the potential to be long-ish, then you should use this
function to protect against the buffer filling up.

Note, there is a more advanced version of this baked into the subprocpool.
"""

from select import select


def pipe_poller(proc, *files, chunk_size=4096):
    """Read from a process without hitting buffer issues.

    Standin for subprocess.Popen.communicate.

    When PIPE'ing from subprocesses, the output goes into a buffer. If the
    buffer gets full, the subprocess will hang trying to write to it.

    This function polls the process, reading output from the buffers into
    memory to prevent them from filling up.

    Args:
        proc:
            The process to poll.
        files:
            The files you want to read from, likely anything you've directed to
            PIPE.
        chunk_size:
            The amount of text to read from the buffer on each pass.

    Returns:
        tuple - The text read from each of the files in the order they were
        specified.

    """
    _files = {
        file: b'' if 'b' in getattr(file, 'mode', 'r') else ''
        for file in files
    }

    def _read(timeout=1.0):
        # read any data from files
        nonlocal chunk_size, files
        for file in select(list(files), [], [], timeout)[0]:
            buffer = file.read(chunk_size)
            if len(buffer) > 0:
                _files[file] += buffer

    while proc.poll() is None:
        # read from the buffers
        _read()
    # double check the buffers now that the process has finished
    _read(timeout=0.01)

    return tuple(_files.values())

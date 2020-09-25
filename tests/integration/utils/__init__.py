# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""General utilities for the integration test infrastructure.

These utilities are not intended for direct use by tests
(hence the underscore function names).
Use the fixtures provided in the conftest instead.

"""

import asyncio
from pathlib import Path


def _rm_if_empty(path):
    """Convenience wrapper for removing empty directories."""
    try:
        path.rmdir()
    except OSError:
        return False
    return True


async def _poll_file(path, timeout=2, step=0.1, exists=True):
    """Poll a file to wait for its creation or removal.

    Arguments:
        timeout (number):
            Maximum time to wait in seconds.
        step (number):
            Polling interval in seconds.
        exists (bool):
            Set to True to check if a file exists, otherwise False.

    Raises:
        Exception:
            If polling hits the timeout.

    """
    elapsed = 0
    while path.exists() != exists:
        await asyncio.sleep(step)
        elapsed += step
        if elapsed > timeout:
            raise Exception(f'Timeout waiting for file creation: {path}')
    return True


def _expanduser(path):
    """Expand $HOME and ~ in paths.

    This code may well become obsolete after job platforms work has been
    merged.

    """
    path = str(path)
    path = path.replace('$HOME', '~')
    path = path.replace('${HOME}', '~')
    path = Path(path).expanduser()
    return path

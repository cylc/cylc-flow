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
#
# Tests for the platform lookup.

import re
from cylc.flow.exceptions import PlatformLookupError


def forward_lookup(platforms, task_platform):
    """
    Find out which job platform to use given a list of possible platforms and
    a task platform string.

    Verifies selected platform is present in global.rc file and returns it,
    raises error if platfrom is not in global.rc or returns 'localhost' if
    no platform is initally selected.

    Args:
        task_platform (str):
            platform item from config [runtime][TASK][platform]
        platforms (dictionary):
            list of possible platforms defined by global.rc

    Returns:
        platform (str):
            string representing a platform from the global config.

    Example:
    Example Input:
    >>> platforms = {
    ...     'suite server platform': None,
    ...     'desktop[0-9][0-9]|laptop[0-9][0-9]': None,
    ...     'sugar': {
    ...         'login hosts': 'localhost',
    ...         'batch system': 'slurm'
    ...     },
    ...     'hpc': {
    ...         'login hosts': ['hpc1', 'hpc2'],
    ...         'batch system': 'pbs'
    ...     },
    ...     'hpc1-bg': {
    ...         'login hosts': 'hpc1',
    ...         'batch system': 'background'
    ...     },
    ...     'hpc2-bg': {
    ...         'login hosts': 'hpc2',
    ...         'batch system': 'background'
    ...     }
    ... }
    >>> task_platform = 'desktop22'
    >>> forward_lookup(platforms, task_platform)
    'desktop22'
    """
    if task_platform is None:
        return 'localhost'
    platforms = list(platforms.keys())
    reversed_platforms = platforms[::-1]
    for platform in reversed_platforms:
        if re.fullmatch(platform, task_platform):
            return task_platform

    raise PlatformLookupError(
        f"No matching platform \"{task_platform}\" found")


def reverse_lookup(task_job, task_remote, platforms):
    """
    Find out which job platform to use given a list of possible platforms
    and the task dictionary with cylc 7 definitions in it.

    Args:
        task_job (dict):
            Suite config [runtime][TASK][job] section
        task_remote (dict):
            Suite config [runtime][TASK][remote] section
        platforms (dict):
            Dictionary containing platfrom definitions.

    Returns:
        platfrom (str):
            string representing a platform from the global config.

    Examples:
        Tim - write some doctests here...

    """
    raise NotImplementedError

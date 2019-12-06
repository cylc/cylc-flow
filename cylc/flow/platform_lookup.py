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
import itertools
from cylc.flow.exceptions import PlatformLookupError


def forward_lookup(task_platform, platforms):
    """
    Find out which job platform to use given a list of possible platforms and
    a task platform string.

    Args:
        task_platform (str):
            platform item from config [runtime][TASK][platform]
        platforms (list):
            list of possible platforms defined by global.rc

    Returns:
        platform (str):
            string representing a platform from the global config.

    Examples:
        Mel - write some doctests here...
    """
    raise NotImplementedError


def reverse_lookup(platforms, job, remote):
    """
    Find out which job platform to use given a list of possible platforms
    and the task dictionary with cylc 7 definitions in it.

          +------------+ Yes    +-----------------------+
    +-----> Tried all  +------->+ RAISE                 |
    |     | platforms? |        | PlatformNotFoundError |
    |     +------------+        +-----------------------+
    |              No|
    |     +----------v---+
    |     | Examine next |
    |     | platform     |
    |     +--------------+
    |                |
    |     +----------v----------------+
    |     | Do all items other than   |
    +<----+ "host" and "batch system" |
    |   No| match for this plaform    |
    |     +---------------------------+
    |                           |Yes
    |                +----------v----------------+ No
    |                | Task host is 'localhost'? +--+
    |                +---------------------------+  |
    |                           |Yes                |
    |              No+----------v----------------+  |
    |            +---+ Task batch system is      |  |
    |            |   | 'background'?             |  |
    |            |   +---------------------------+  |
    |            |              |Yes                |
    |            |   +----------v----------------+  |
    |            |   | RETURN 'localhost'        |  |
    |            |   +---------------------------+  |
    |            |                                  |
    |    +-------v-------------+     +--------------v-------+
    |  No| batch systems match |  Yes| batch system and     |
    +<---+ and 'localhost' in  |  +--+ host both match      |
    |    | platform hosts?     |  |  +----------------------+
         +---------------------+  |                 |No
    |            |Yes             |  +--------------v-------+
    |    +-------v--------------+ |  | batch system match   |
    |    | RETURN this platform <-+--+ and regex of platform|
    |    +----------------------+ Yes| name matches host    |
    |                                +----------------------+
    |                                  |No
    +<---------------------------------+

    Args:
        job (dict):
            Suite config [runtime][TASK][job] section
        remote (dict):
            Suite config [runtime][TASK][remote] section
        platforms (dict):
            Dictionary containing platfrom definitions.

    Returns:
        platfrom (str):
            string representing a platform from the global config.

    Raises:
        PlatformLookupError:
            If no matching platform can be a found an error is raised.

    Example:
        >>> platforms = {
        ...         'desktop[0-9][0-9]|laptop[0-9][0-9]': {},
        ...         'sugar': {
        ...             'login hosts': 'localhost',
        ...             'batch system': 'slurm'
        ...         }
        ... }
        >>> job = {'batch system': 'slurm'}
        >>> remote = {'host': 'sugar'}
        >>> reverse_lookup(platforms, job, remote)
        'sugar'
        >>> remote = {}
        >>> reverse_lookup(platforms, job, remote)
        'localhost'
    """
    # These settings are removed from the incoming dictionaries for special
    # handling later - we want more than a simple match:
    #   - In the case of host we also want a regex match to the platform name
    #   - In the case of batch system we want to match the name of the system
    #     to a platform when host is localhost.
    if 'host' in remote.keys():
        task_host = remote.pop('host')
    else:
        task_host = 'localhost'
    if 'batch system' in job.keys():
        task_batch_system = job.pop('batch system')
    else:
        task_batch_system = 'background'

    # Riffle through the platforms looking for a match to our task settings.
    for platform_name, platform_spec in platforms.items():
        # Handle all the items requiring an exact match.
        generic_items_match = True
        for task_section in [job, remote]:
            shared_items = set(
                task_section.keys()).intersection(set(platform_spec.keys()))
            for shared_item in shared_items:
                # breakpoint()
                if platform_spec[shared_item] != task_section[shared_item]:
                    generic_items_match = False

        # All items other than batch system and host must be an exact match
        if not generic_items_match:
            continue

        # We have some special logic to identify whether task host and task
        # batch system match the platform in question.
        if task_host == 'localhost':
            if task_batch_system == 'background':
                return 'localhost'
            elif (
                task_batch_system == platform_spec['batch system'] and
                'hosts' in platform_spec.keys() and
                'localhost' in platform_spec['hosts']
            ):
                # If we have localhost with a non-background batch system we
                # use the batch system to give a sensible guess at the platform
                return platform_name

        else:
            if (
                'hosts' in platform_spec.keys() and
                task_host in platform_spec['hosts'] and
                task_batch_system == platform_spec['batch system']
            ):
                return platform_name

            elif (
                re.fullmatch(platform_name, task_host) and
                task_batch_system == platform_spec['batch system']
            ):
                return task_host

    raise PlatformLookupError('No platform found matching your task')

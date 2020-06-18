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
#
# Tests for the platform lookup.

from copy import deepcopy
import re

from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg


def forward_lookup(platform_name=None, platforms=None):
    """
    Find out which job platform to use given a list of possible platforms and
    a task platform string.

    Verifies selected platform is present in global.rc file and returns it,
    raises error if platfrom is not in global.rc or returns 'localhost' if
    no platform is initally selected.

    Args:
        platform_name (str):
            name of platform to be retrieved.
        platforms ():
            globalrc platforms given as a dict for logic testing purposes
    Returns:
        platform (dict):
            object containing settings for a platform, loaded from
            Global Config.

    TODO:
        - Refactor testing for this method. Ideally including a method
          example.
        - Work out what to do with cases where localhost not set.
    """
    if platforms is None:
        platforms = glbl_cfg().get(['job platforms'])

    if platform_name is None:
        platform_data = deepcopy(platforms['localhost'])
        platform_data['name'] = 'localhost'
        return platform_data

    # The list is reversed to allow user-set platforms (which are loaded
    # later than site set platforms) to be matched first and override site
    # defined platforms.
    for platform_name_re in reversed(list(platforms)):
        if re.fullmatch(platform_name_re, platform_name):
            platform_data = platforms[platform_name_re]
            if not platform_data:
                platform_data = deepcopy(platforms['localhost'])
                platform_data['remote hosts'] = platform_name
            else:
                platform_data = deepcopy(platform_data)
            platform_data['name'] = platform_name
            return platform_data

    raise PlatformLookupError(
        f"No matching platform \"{platform_name}\" found")


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
        ...             'remote hosts': 'localhost',
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
    if 'host' in remote.keys() and remote['host']:
        task_host = remote.pop('host')
    else:
        task_host = 'localhost'
    if 'batch system' in job.keys():
        task_batch_system = job.pop('batch system')
    else:
        # Necessary? Perhaps not if batch system default is 'background'
        task_batch_system = 'background'

    # Riffle through the platforms looking for a match to our task settings.
    # reverse dict order so that user config platforms added last are examined
    # before site config platforms.
    for platform_name, platform_spec in reversed(list(platforms.items())):
        # Handle all the items requiring an exact match.
        for task_section in [job, remote]:
            shared_items = set(
                task_section).intersection(set(platform_spec.keys()))
            generic_items_match = all((
                platform_spec[item] == task_section[item]
                for item in shared_items
            ))
        # All items other than batch system and host must be an exact match
        if not generic_items_match:
            continue
        # We have some special logic to identify whether task host and task
        # batch system match the platform in question.
        if (
                task_host == 'localhost' and
                task_batch_system == 'background'
        ):
            return 'localhost'

        elif (
            'remote hosts' in platform_spec.keys() and
            task_host in platform_spec['remote hosts'] and
            task_batch_system == platform_spec['batch system']
        ):
            # If we have localhost with a non-background batch system we
            # use the batch system to give a sensible guess at the platform
            return platform_name

        elif (
                re.fullmatch(platform_name, task_host) and
                task_batch_system == platform_spec['batch system']
        ):
            return task_host

    raise PlatformLookupError('No platform found matching your task')

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
#
# Tests for the platform lookup.

import random
import re
from copy import deepcopy
from typing import (
    Any, Dict, Iterable, List, Optional, Tuple, Union)

from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.hostuserutil import is_remote_host


FORBIDDEN_WITH_PLATFORM: Tuple[Tuple[str, str, List[Optional[str]]], ...] = (
    ('remote', 'host', ['localhost', None]),
    ('job', 'batch system', [None]),
    ('job', 'batch submit command template', [None])
)

# Regex to check whether a string is a command
HOST_REC_COMMAND = re.compile(r'(`|\$\()\s*(.*)\s*([`)])$')
PLATFORM_REC_COMMAND = re.compile(r'(\$\()\s*(.*)\s*([)])$')


# BACK COMPAT: get_platform
#     At Cylc 9 remove all Cylc7 upgrade logic.
# from:
#     Cylc8
# to:
#     Cylc9
# remove at:
#     Cylc9
def get_platform(
    task_conf: Union[str, Dict[str, Any], None] = None,
    task_id: str = 'unknown task'
) -> Optional[Dict[str, Any]]:
    """Get a platform.

    Looking at a task config this method decides whether to get platform from
    name, or Cylc7 config items.

    Args:
        task_conf: If str this is assumed to be the platform name, otherwise
            this should be a configuration for a task.
        task_id: Task identification string - help produce more helpful error
            messages.

    Returns:
        platform: A platform definition dictionary. Uses either
            get_platform() or platform_from_job_info(), but to the
            user these look the same.
    """
    if task_conf is None or isinstance(task_conf, str):
        # task_conf is a platform name, or get localhost if None
        return platform_from_name(task_conf)

    elif 'platform' in task_conf and task_conf['platform']:
        # Check whether task has conflicting Cylc7 items.
        fail_if_platform_and_host_conflict(task_conf, task_id)

        if is_platform_definition_subshell(task_conf['platform']):
            # Platform definition is using subshell e.g. platform = $(foo);
            # won't be evaluated until job submit so cannot get or
            # validate platform
            return None

        # If platform name exists and doesn't clash with Cylc7 Config items.
        return platform_from_name(task_conf['platform'])

    else:
        if get_platform_deprecated_settings(task_conf) == []:
            # No deprecated items; platform is localhost
            return platform_from_name()
        else:
            # Need to calculate platform
            task_job_section, task_remote_section = {}, {}
            if 'job' in task_conf:
                task_job_section = task_conf['job']
            if 'remote' in task_conf:
                task_remote_section = task_conf['remote']
            return platform_from_name(
                platform_from_job_info(
                    glbl_cfg(cached=False).get(['platforms']),
                    task_job_section,
                    task_remote_section
                )
            )


def platform_from_name(
    platform_name: Optional[str] = None,
    platforms: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Find out which job platform to use given a list of possible platforms and
    a task platform string.

    Verifies selected platform is present in global.cylc file and returns it,
    raises error if platform is not in global.cylc or returns 'localhost' if
    no platform is initially selected.

    Args:
        platform_name: name of platform to be retrieved.
        platforms: global.cylc platforms given as a dict.

    Returns:
        platform: object containing settings for a platform, loaded from
            Global Config.
    """
    if platforms is None:
        platforms = glbl_cfg().get(['platforms'])
    platform_groups = glbl_cfg().get(['platform groups'])

    if platform_name is None:
        platform_name = 'localhost'

    platform_group = None
    for platform_name_re in reversed(list(platform_groups)):
        if re.fullmatch(platform_name_re, platform_name):
            platform_group = deepcopy(platform_name)
            platform_name = random.choice(
                platform_groups[platform_name_re]['platforms']
            )

    # The list is reversed to allow user-set platforms (which are loaded
    # later than site set platforms) to be matched first and override site
    # defined platforms.
    for platform_name_re in reversed(list(platforms)):
        # We substitue commas with or without spaces to
        # allow lists of platforms
        if (
            re.fullmatch(
                re.sub(
                    r'\s*(?!{[\s\d]*),(?![\s\d]*})\s*',
                    '|',
                    platform_name_re
                ),
                platform_name
            )
        ):
            # Deepcopy prevents contaminating platforms with data
            # from other platforms matching platform_name_re
            platform_data = deepcopy(platforms[platform_name_re])

            # If hosts are not filled in make remote
            # hosts the platform name.
            # Example: `[platforms][workplace_vm_123]<nothing>`
            #   should create a platform where
            #   `remote_hosts = ['workplace_vm_123']`
            if (
                'hosts' not in platform_data.keys() or
                not platform_data['hosts']
            ):
                platform_data['hosts'] = [platform_name]
            # Fill in the "private" name field.
            platform_data['name'] = platform_name
            if platform_group:
                platform_data['group'] = platform_group
            return platform_data

    raise PlatformLookupError(
        f"No matching platform \"{platform_name}\" found")


def platform_from_job_info(
    platforms: Dict[str, Any],
    job: Dict[str, Any],
    remote: Dict[str, Any]
) -> str:
    """
    Find out which job platform to use given a list of possible platforms
    and the task dictionary with cylc 7 definitions in it.

    (Note: "batch system" (Cylc 7) and "job runner" (Cylc 8)
    mean the same thing)

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
        job: Workflow config [runtime][TASK][job] section.
        remote: Workflow config [runtime][TASK][remote] section.
        platforms: Dictionary containing platform definitions.

    Returns:
        platform: string representing a platform from the global config.

    Raises:
        PlatformLookupError:
            If no matching platform can be a found an error is raised.

    Example:
        >>> platforms = {
        ...         'desktop[0-9][0-9]|laptop[0-9][0-9]': {},
        ...         'sugar': {
        ...             'hosts': 'localhost',
        ...             'job runner': 'slurm'
        ...         }
        ... }
        >>> job = {'batch system': 'slurm'}
        >>> remote = {'host': 'localhost'}
        >>> platform_from_job_info(platforms, job, remote)
        'sugar'
        >>> remote = {}
        >>> platform_from_job_info(platforms, job, remote)
        'sugar'
        >>> remote ={'host': 'desktop92'}
        >>> job = {}
        >>> platform_from_job_info(platforms, job, remote)
        'desktop92'
    """

    # These settings are removed from the incoming dictionaries for special
    # handling later - we want more than a simple match:
    #   - In the case of "host" we also want a regex match to the platform name
    #   - In the case of "batch system" we want to match the name of the
    #     system/job runner to a platform when host is localhost.
    if 'host' in remote.keys() and remote['host']:
        task_host = remote['host']
    else:
        task_host = 'localhost'
    if 'batch system' in job.keys() and job['batch system']:
        task_job_runner = job['batch system']
    else:
        # Necessary? Perhaps not if batch system default is 'background'
        task_job_runner = 'background'
    # Riffle through the platforms looking for a match to our task settings.
    # reverse dict order so that user config platforms added last are examined
    # before site config platforms.
    for platform_name, platform_spec in reversed(list(platforms.items())):
        # Handle all the items requiring an exact match.
        # All items other than batch system and host must be an exact match
        if not generic_items_match(platform_spec, job, remote):
            continue
        # We have some special logic to identify whether task host and task
        # batch system match the platform in question.
        if (
                not is_remote_host(task_host) and
                task_job_runner == 'background'
        ):
            return 'localhost'

        elif (
            'hosts' in platform_spec.keys() and
            task_host in platform_spec['hosts'] and
            task_job_runner == platform_spec['job runner']
        ):
            # If we have localhost with a non-background batch system we
            # use the batch system to give a sensible guess at the platform
            return platform_name

        elif (
            re.fullmatch(platform_name, task_host) and (
                (
                    task_job_runner == 'background' and
                    'job runner' not in platform_spec
                ) or
                task_job_runner == platform_spec['job runner']
            )
        ):
            return task_host

    raise PlatformLookupError('No platform found matching your task')


def generic_items_match(
    platform_spec: Dict[str, Any],
    job: Dict[str, Any],
    remote: Dict[str, Any]
) -> bool:
    """Checks generic items from job/remote against a platform.

    We carry out extra checks on ``[remote]host`` and ``[job]batch system``
    but all other set config items must match between a platform and old
    settings for that platform to match the legacy settings.

    Args:
        platform_spec: Dictionary of platform spec.
        job: Dictionary of config spec section ``[runtime][TASK][job]``
        remote: Dictionary of config spec section ``[runtime][TASK][remote]``

    Returns:
        Does this platform have generic items (not ``[job]batch system``
        or ``[remote]host`` which are treated specially) that are the same.
    """
    # Don't check Host and batch system - they have their own logic.
    if 'host' in remote:
        remote_generic = {
            k: v for k, v in remote.items()
            if k != 'host' and v is not None
        }
    else:
        remote_generic = remote
    if 'batch system' in job:
        job_generic = {
            k: v for k, v in job.items()
            if k != 'batch system' and v is not None
        }
    else:
        job_generic = job

    for task_section in [job_generic, remote_generic]:
        # Get a set of items actually set in both platform and task_section.
        shared_items = set(task_section).intersection(set(platform_spec))
        # If any set items do not match, we can't use this platform.
        if not all([
            platform_spec[item] == task_section[item]
            for item in shared_items
        ]):
            return False
    return True


def get_host_from_platform(platform, method='random'):
    """Placeholder for a more sophisticated function which returns a host
    given a platform dictionary.

    Args:
        platform (dict):
            A dict representing a platform.
        method (str):
            Name a function to use when selecting hosts from list provided
            by platform.
            - 'random' (default): Pick a random host from list
            - 'first': Return the first host in the list

    Returns:
        hostname (str):

    TODO:
        Other host selection methods:
            - Random Selection with check for host availability

    """
    if method == 'random':
        return random.choice(platform['hosts'])
    elif method == 'first':
        return platform['hosts'][0]
    else:
        raise NotImplementedError(
            f'method {method} is not a valid input for get_host_from_platform'
        )


def fail_if_platform_and_host_conflict(task_conf, task_name):
    """Raise an error if task spec contains platform and forbidden host items.

    Args:
        task_conf(dict, OrderedDictWithDefaults):
            A specification to be checked.
        task_name(string):
            A name to be given in an error.

    Raises:
        PlatformLookupError - if platform and host items conflict

    """
    if 'platform' in task_conf and task_conf['platform']:
        fail_items = ''
        for section, key, _ in FORBIDDEN_WITH_PLATFORM:
            if (
                section in task_conf and
                key in task_conf[section] and
                task_conf[section][key] is not None
            ):
                fail_items += (
                    f' * platform = {task_conf["platform"]} AND'
                    f' [{section}]{key} = {task_conf[section][key]}\n'
                )
        if fail_items != '':
            raise PlatformLookupError(
                f"A mixture of Cylc 7 (host) and Cylc 8 (platform) "
                f"logic should not be used. In this case the task "
                f"\"{task_name}\" has the following settings which "
                f"are not compatible:\n{fail_items}"
            )


def get_platform_deprecated_settings(
    task_conf: Dict[str, Any], task_name: str = 'unknown task'
) -> List[str]:
    """Return deprecated [runtime][<task_name>] settings that should be
    upgraded to platforms.

    Args:
        task_conf: Runtime configuration for the task.
        task_name: The task name.
    """
    result: List[str] = []
    for section, key, exceptions in FORBIDDEN_WITH_PLATFORM:
        if (
            section in task_conf and
            key in task_conf[section] and
            task_conf[section][key] not in exceptions
        ):
            result.append(
                f'[runtime][{task_name}][{section}]{key} = '
                f'{task_conf[section][key]}'
            )
    return result


def is_platform_definition_subshell(value: str) -> bool:
    """Is the platform definition using subshell? E.g. platform = $(foo)

    Raise PlatformLookupError if using backticks.
    """
    if PLATFORM_REC_COMMAND.match(value):
        return True
    if HOST_REC_COMMAND.match(value):
        raise PlatformLookupError(
            f"platform = {value}: backticks are not supported; please use $()"
        )
    return False


def get_install_target_from_platform(platform: Dict[str, Any]) -> str:
    """Sets install target to configured or default platform name.

    Returns install target.
    """
    if not platform['install target']:
        platform['install target'] = platform['name']

    return platform['install target']


def get_install_target_to_platforms_map(
        platform_names: Iterable[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """Get a dictionary of unique install targets and the platforms which use
    them.

    Args:
        platform_names: List of platform names to look up in the global config.

    Return {install_target_1: [platform_1_dict, platform_2_dict, ...], ...}
    """
    platform_names = set(platform_names)
    platforms = [platform_from_name(p_name) for p_name in platform_names]
    install_targets = set(get_install_target_from_platform(platform)
                          for platform in platforms)
    return {
        target: [platform for platform in platforms
                 if get_install_target_from_platform(platform) == target]
        for target in install_targets
    }


def is_platform_with_target_in_list(
        install_target: str,
        distinct_platforms_list: Iterable[Dict[str, Any]]
) -> bool:
    """Determines whether install target is in the list of platforms"""
    for distinct_platform in distinct_platforms_list:
        if install_target == distinct_platform['install target']:
            return True
    return False


def get_all_platforms_for_install_target(
    install_target: str
) -> List[Dict[str, Any]]:
    """Return list of platform dictionaries for given install target."""
    platforms: List[Dict[str, Any]] = []
    all_platforms = glbl_cfg(cached=True).get(['platforms'], sparse=False)
    for k, v in all_platforms.items():
        if (v.get('install target', k) == install_target):
            v_copy = deepcopy(v)
            v_copy['name'] = k
            platforms.append(v_copy)
    return platforms


def get_random_platform_for_install_target(
    install_target: str
) -> Dict[str, Any]:
    """Return a randomly selected platform (dict) for given install target."""
    platforms = get_all_platforms_for_install_target(install_target)
    try:
        return random.choice(platforms)
    except IndexError:
        # No platforms to choose from
        raise PlatformLookupError(
            f'Could not select platform for install target: {install_target}'
        )


def get_localhost_install_target() -> str:
    """Returns the install target of localhost platform"""
    localhost = platform_from_name()
    return get_install_target_from_platform(localhost)

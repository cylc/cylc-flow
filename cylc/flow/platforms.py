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

import random
import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, TYPE_CHECKING

from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.hostuserutil import is_remote_host

if TYPE_CHECKING:
    from collections import OrderedDict


FORBIDDEN_WITH_PLATFORM = (
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
def get_platform(task_conf=None, task_id='unknown task', warn_only=False):
    """Get a platform.

    Looking at a task config this method decides whether to get platform from
    name, or Cylc7 config items.

    Args:
        task_conf (str, dict or dict-like such as OrderedDictWithDefaults):
            If str this is assumed to be the platform name, otherwise this
            should be a configuration for a task.
        task_id (str):
            Task identification string - help produce more helpful error
            messages.
        warn_only(bool):
            If true, warnings about tasks requiring upgrade will be returned.

    Returns:
        platform (platform, or string):
            Actually it returns either get_platform() or
            platform_from_job_info(), but to the user these look the same.
            When working in warn_only mode, warnings are returned as strings.

    """
    if task_conf is None:
        # Just a simple way of accessing localhost items.
        output = platform_from_name()

    elif isinstance(task_conf, str):
        # If task_conf is str assume that it is a platform name.
        output = platform_from_name(task_conf)

    elif 'platform' in task_conf and task_conf['platform']:
        if PLATFORM_REC_COMMAND.match(task_conf['platform']) and warn_only:
            # In warning mode this function might have been passed an
            # un-expanded platform string - warn that they won't deal with
            # with this until job submit.
            return None
        if HOST_REC_COMMAND.match(task_conf['platform']) and warn_only:
            raise PlatformLookupError(
                f"platform = {task_conf['platform']}: "
                "backticks are not supported; "
                "please use $()"
            )

        # Check whether task has conflicting Cylc7 items.
        fail_if_platform_and_host_conflict(task_conf, task_id)

        # If platform name exists and doesn't clash with Cylc7 Config items.
        output = platform_from_name(task_conf['platform'])

    else:
        # If forbidden items present calculate platform else platform is
        # local
        platform_is_localhost = True

        warn_msgs = []
        for section, key, exceptions in FORBIDDEN_WITH_PLATFORM:
            # if section not in task_conf:
            #     task_conf[section] = {}
            if (
                section in task_conf and
                key in task_conf[section] and
                task_conf[section][key] not in exceptions
            ):
                platform_is_localhost = False
                if warn_only:
                    warn_msgs.append(
                        f"[runtime][{task_id}][{section}]{key} = "
                        f"{task_conf[section][key]}\n"
                    )

        if platform_is_localhost:
            output = platform_from_name()

        elif warn_only:
            output = (
                f'Task {task_id} Deprecated "host" and "batch system" will be '
                'removed at Cylc 9 - upgrade to platform:'
                f'\n{"".join(warn_msgs)}'
            )

        else:
            task_job_section, task_remote_section = {}, {}
            if 'job' in task_conf:
                task_job_section = task_conf['job']
            if 'remote' in task_conf:
                task_remote_section = task_conf['remote']
            output = platform_from_name(
                platform_from_job_info(
                    glbl_cfg(cached=False).get(['platforms']),
                    task_job_section,
                    task_remote_section
                )
            )

    return output


def platform_from_name(platform_name=None, platforms=None):
    """
    Find out which job platform to use given a list of possible platforms and
    a task platform string.

    Verifies selected platform is present in global.cylc file and returns it,
    raises error if platfrom is not in global.cylc or returns 'localhost' if
    no platform is initally selected.

    Args:
        platform_name (str):
            name of platform to be retrieved.
        platforms ():
            global.cylc platforms given as a dict for logic testing purposes

    Returns:
        platform (dict):
            object containing settings for a platform, loaded from
            Global Config.
    """
    if platforms is None:
        platforms = glbl_cfg().get(['platforms'])
    platform_groups = glbl_cfg().get(['platform groups'])

    if platform_name is None:
        platform_data = deepcopy(platforms['localhost'])
        platform_data['name'] = 'localhost'
        return platform_data

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
        if re.fullmatch(platform_name_re, platform_name):
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


def platform_from_job_info(platforms, job, remote):
    """
    Find out which job platform to use given a list of possible platforms
    and the task dictionary with cylc 7 definitions in it.

    (Note: "batch system" and "job runner" mean the same thing)

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
            Dictionary containing platform definitions.

    Returns:
        platform (str):
            string representing a platform from the global config.

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
        >>> remote = {'host': 'sugar'}
        >>> platform_from_job_info(platforms, job, remote)
        'sugar'
        >>> remote = {}
        >>> platform_from_job_info(platforms, job, remote)
        'localhost'
    """

    # These settings are removed from the incoming dictionaries for special
    # handling later - we want more than a simple match:
    #   - In the case of "host" we also want a regex match to the platform name
    #   - In the case of "batch system" we want to match the name of the
    #     system/job runner to a platform when host is localhost.
    if 'host' in remote.keys() and remote['host']:
        task_host = remote.pop('host')
    else:
        task_host = 'localhost'
    if 'batch system' in job.keys() and job['batch system']:
        task_job_runner = job.pop('batch system')
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
                re.fullmatch(platform_name, task_host) and
                task_job_runner == platform_spec['job runner']
        ):
            return task_host

    raise PlatformLookupError('No platform found matching your task')


def generic_items_match(platform_spec, job, remote):
    """Checks generic items from job/remote against a platform.
    """
    for task_section in [job, remote]:
        shared_items = set(task_section).intersection(set(platform_spec))
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


def get_install_target_from_platform(platform: Dict[str, Any]) -> str:
    """Sets install target to configured or default platform name.

    Returns install target.
    """
    if not platform['install target']:
        platform['install target'] = platform['name']

    return platform['install target']


def get_install_target_to_platforms_map(
        platform_names: Iterable[str]
) -> Dict[str, List['OrderedDict[str, Any]']]:
    """Get a dictionary of unique install targets and the platforms which use
    them.

    Args:
        platform_names: List of platform names to look up in the global config.

    Return {install_target_1: [platform_1_dict, platform_2_dict, ...], ...}
    """
    platform_names = set(platform_names)
    platforms = [get_platform(p_name) for p_name in platform_names]
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


def get_all_platforms_for_install_target(install_target):
    """Return list of platform dictionaries for given install target."""
    platforms = []
    all_platforms = glbl_cfg(cached=True).get(['platforms'], sparse=False)
    for k, v in all_platforms.iteritems():
        if (v.get('install target', k) == install_target):
            v_copy = deepcopy(v)
            v_copy['name'] = k
            platforms.append(v_copy)
    return platforms


def get_random_platform_for_install_target(install_target):
    """Return a randomly selected platform (dict) for given install target."""
    platforms = get_all_platforms_for_install_target(install_target)
    return random.choice(platforms)


def get_localhost_install_target():
    """Returns the install target of localhost platform"""
    localhost = get_platform()
    return get_install_target_from_platform(localhost)

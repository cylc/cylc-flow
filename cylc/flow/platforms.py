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
"""Functions relating to (job) platforms."""

import random
import re
from copy import deepcopy
from typing import (
    TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Union, overload
)

from cylc.flow import LOG

from cylc.flow.exceptions import (
    GlobalConfigError,
    PlatformLookupError, CylcError, NoHostsError, NoPlatformsError)
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.hostuserutil import is_remote_host

if TYPE_CHECKING:
    from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults

UNKNOWN_TASK = 'unknown task'

FORBIDDEN_WITH_PLATFORM: Dict[str, Dict[str, Set[Optional[str]]]] = {
    'remote': {
        # setting: exclusions
        'host': {'localhost', None},
        'retrieve job logs': {None},
        'retrieve job logs max size': {None},
        'retrieve job logs retry delays': {None},
    },
    'job': {
        'batch system': {None},
        'batch submit command template': {None}
    }
}

DEFAULT_JOB_RUNNER = 'background'
SINGLE_HOST_JOB_RUNNERS = ['background', 'at']

# Regex to check whether a string is a command
HOST_REC_COMMAND = re.compile(r'(`|\$\()\s*(.*)\s*([`)])$')
PLATFORM_REC_COMMAND = re.compile(r'(\$\()\s*(.*)\s*([)])$')

HOST_SELECTION_METHODS = {
    'definition order': lambda goodhosts: goodhosts[0],
    'random': random.choice
}


def log_platform_event(
    event: str,
    platform: dict,
    host: Optional[str] = None,
    level: str = 'info'
):
    """Log a simple platform event."""
    # matches cylc.flow.exceptions.PlatformError format
    getattr(LOG, level)(
        f'platform: {platform["name"]} - {event}'
        + (f' (on {host})' if host else '')
    )


@overload
def get_platform(
    task_conf: Optional[str] = None,
    task_name: str = UNKNOWN_TASK,
    bad_hosts: Optional[Set[str]] = None
) -> Dict[str, Any]:
    ...


@overload
def get_platform(
    task_conf: Union[dict, 'OrderedDictWithDefaults'],
    task_name: str = UNKNOWN_TASK,
    bad_hosts: Optional[Set[str]] = None
) -> Optional[Dict[str, Any]]:
    ...


# BACK COMPAT: get_platform
#     At Cylc 8.x remove all Cylc7 upgrade logic.
# from:
#     Cylc8
# to:
#     Cylc8.x
# remove at:
#     Cylc8.x
def get_platform(
    task_conf: Union[str, dict, 'OrderedDictWithDefaults', None] = None,
    task_name: str = UNKNOWN_TASK,
    bad_hosts: Optional[Set[str]] = None
) -> Optional[Dict[str, Any]]:
    """Get a platform.

    Looking at a task config this method decides whether to get platform from
    name, or Cylc7 config items.

    Args:
        task_conf: If str this is assumed to be the platform name, otherwise
            this should be a configuration for a task.
        task_name: Help produce more helpful error messages.
        bad_hosts: A set of hosts known to be unreachable (had an ssh 255
            error)

    Returns:
        platform: A platform definition dictionary. Uses either
            get_platform() or platform_name_from_job_info(), but to the
            user these look the same.

    Raises:
        NoPlatformsError:
            Platform group has no platforms with usable hosts.
            This should be caught if this function is used on a raw on config,
            or in any other context where a platform group might be selected.
        PlatformLookupError:
            Raised if the name of a platform cannot be selected based on the
            information given.
    """
    if task_conf is None or isinstance(task_conf, str):  # noqa: SIM 114
        # task_conf is a platform name, or get localhost if None
        return platform_from_name(task_conf, bad_hosts=bad_hosts)

    # NOTE: Do NOT use .get() on OrderedDictWithDefaults -
    # https://github.com/cylc/cylc-flow/pull/4975
    elif 'platform' in task_conf and task_conf['platform']:
        # Check whether task has conflicting Cylc7 items.
        fail_if_platform_and_host_conflict(task_conf, task_name)

        if is_platform_definition_subshell(task_conf['platform']):
            # Platform definition is using subshell e.g. platform = $(foo);
            # won't be evaluated until job submit so cannot get or
            # validate platform
            return None

        # If platform name exists and doesn't clash with Cylc7 Config items.
        return platform_from_name(task_conf['platform'], bad_hosts=bad_hosts)

    else:
        if get_platform_deprecated_settings(task_conf) == []:
            # No deprecated items; platform is localhost
            return platform_from_name()
        else:
            # Need to calculate platform
            # NOTE: Do NOT use .get() on OrderedDictWithDefaults - see above
            task_job_section = task_conf['job'] if 'job' in task_conf else {}
            task_remote_section = (
                task_conf['remote'] if 'remote' in task_conf else {})
            return platform_from_name(
                platform_name_from_job_info(
                    glbl_cfg(cached=False).get(['platforms']),
                    task_job_section,
                    task_remote_section
                ),
                bad_hosts=bad_hosts
            )


def platform_from_name(
    platform_name: Optional[str] = None,
    platforms: Optional[Dict[str, Dict[str, Any]]] = None,
    bad_hosts: Optional[Set[str]] = None
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
        bad_hosts: A set of hosts known to be unreachable (had an ssh 255
            error)

    Returns:
        platform: object containing settings for a platform, loaded from
            Global Config.

    Raises:
        NoPlatformsError: Platform group has no platforms with usable hosts.
    """
    if platforms is None:
        platforms = glbl_cfg().get(['platforms'])
    platform_groups = glbl_cfg().get(['platform groups'])

    if platform_name is None:
        platform_name = 'localhost'

    # The list is reversed to allow user-set platform groups (which are
    # appended to site set platform groups) to be matched first and override
    # site defined platform groups.
    for platform_name_re in reversed(list(platform_groups)):
        # Platform is member of a group.
        if re.fullmatch(platform_name_re, platform_name):
            platform_name = get_platform_from_group(
                platform_groups[platform_name_re], group_name=platform_name,
                bad_hosts=bad_hosts
            )
            break

    for platform_name_re in list(platforms):
        if (
            # If the platform_name_re contains special regex chars
            re.escape(platform_name_re) != platform_name_re
            and re.match(platform_name_re, 'localhost')
        ):
            raise PlatformLookupError(
                'The "localhost" platform cannot be defined using a '
                'regular expression. See the documentation for '
                '"global.cylc[platforms][localhost]" for more information.'
            )

    # The list is reversed to allow user-set platforms (which are appended to
    # than site set platforms) to be matched first and override site defined
    # platforms.
    for platform_name_re in reversed(list(platforms)):
        # We substitute commas with or without spaces to
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
            return platform_data

    raise PlatformLookupError(
        f"No matching platform \"{platform_name}\" found")


def get_platform_from_group(
    group: Union[dict, 'OrderedDictWithDefaults'],
    group_name: str,
    bad_hosts: Optional[Set[str]] = None
) -> str:
    """Get platform name from group, according to the selection method.

    Args:
        group: A platform group dictionary.
        group_name: Name of the group.
        bad_hosts: The set of hosts found to be unreachable.

    Returns:
        Name of platform selected, or False if all hosts on all platforms are
        in bad_hosts.

    Raises:
        NoPlatformsError: If there are no platforms with any usable
        hosts in the platform group.

    TODO: Uses host_selection methods; should also allow custom select methods.
    """
    if bad_hosts:
        good_platforms = []
        for platform in group['platforms']:
            if any(
                host not in bad_hosts
                for host in platform_from_name(platform)['hosts']
            ):
                good_platforms.append(platform)

        platform_names = list(good_platforms)
    else:
        platform_names = group['platforms']

    # Return False if there are no platforms available to be selected.
    if not platform_names:
        raise NoPlatformsError(group_name)

    # Get the selection method
    method = group['selection']['method']
    if method not in HOST_SELECTION_METHODS:
        raise CylcError(
            f'\"{method}\" is not a supported platform selection method.'
        )
    else:
        return HOST_SELECTION_METHODS[method](platform_names)


def platform_name_from_job_info(
    platforms: Union[dict, 'OrderedDictWithDefaults'],
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
        >>> platform_name_from_job_info(platforms, job, remote)
        'sugar'
        >>> remote = {}
        >>> platform_name_from_job_info(platforms, job, remote)
        'sugar'
        >>> remote ={'host': 'desktop92'}
        >>> job = {}
        >>> platform_name_from_job_info(platforms, job, remote)
        'desktop92'
    """

    # These settings are removed from the incoming dictionaries for special
    # handling later - we want more than a simple match:
    #   - In the case of "host" we also want a regex match to the platform name
    #   - In the case of "batch system" we want to match the name of the
    #     system/job runner to a platform when host is localhost.

    # NOTE: Do NOT use .get() on OrderedDictWithDefaults -
    # https://github.com/cylc/cylc-flow/pull/4975
    if 'host' in remote and remote['host']:
        task_host = remote['host']
    else:
        task_host = 'localhost'
    if 'batch system' in job and job['batch system']:
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
            'hosts' in platform_spec and
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


def get_host_from_platform(
    platform: Dict[str, Any], bad_hosts: Optional[Set[str]] = None
) -> str:
    """Placeholder for a more sophisticated function which returns a host
    given a platform dictionary.

    Args:
        platform: A dict representing a platform.
        bad_hosts: A set of hosts Cylc knows to be unreachable.

    Returns:
        hostname: The name of a host.

    Raises:
        NoHostsError:
            This error should be caught by caller to prevent workflow shutdown.
    """
    # Get list of goodhosts:
    if bad_hosts:
        goodhosts = [i for i in platform['hosts'] if i not in bad_hosts]
    else:
        goodhosts = platform['hosts']

    # Get the selection method
    method = platform['selection']['method']
    if not goodhosts:
        raise NoHostsError(platform)
    else:
        if method not in HOST_SELECTION_METHODS:
            raise CylcError(
                f'method \"{method}\" is not a supported host '
                'selection method.'
            )
        else:
            return HOST_SELECTION_METHODS[method](goodhosts)


def fail_if_platform_and_host_conflict(
    task_conf: Union[dict, 'OrderedDictWithDefaults'], task_name: str
) -> None:
    """Raise an error if [runtime][<task>] spec contains platform and
    forbidden host items.

    Args:
        task_conf: A specification to be checked.
        task_name: A name to be given in an error.

    Raises:
        PlatformLookupError - if platform and host items conflict

    """
    # NOTE: Do NOT use .get() on OrderedDictWithDefaults -
    # https://github.com/cylc/cylc-flow/pull/4975
    if 'platform' in task_conf and task_conf['platform']:
        fail_items = [
            f'\n * [{section}]{key}'
            for section, keys in FORBIDDEN_WITH_PLATFORM.items()
            if section in task_conf
            for key, _ in keys.items()
            if (
                key in task_conf[section] and
                task_conf[section][key] is not None
            )
        ]
        if fail_items:
            raise PlatformLookupError(
                f"Task '{task_name}' has the following deprecated '[runtime]' "
                "setting(s) which cannot be used with "
                f"'platform = {task_conf['platform']}':{''.join(fail_items)}"
            )


def get_platform_deprecated_settings(
    task_conf: Union[dict, 'OrderedDictWithDefaults'],
    task_name: str = UNKNOWN_TASK
) -> List[str]:
    """Return deprecated [runtime][<task_name>] settings that should be
    upgraded to platforms.

    Args:
        task_conf: Runtime configuration for the task.
        task_name: The task name.
    """
    return [
        f'[runtime][{task_name}][{section}]{key} = {task_conf[section][key]}'
        for section, keys in FORBIDDEN_WITH_PLATFORM.items()
        if section in task_conf
        for key, exclusions in keys.items()
        if (
            key in task_conf[section] and
            task_conf[section][key] not in exclusions
        )
    ]


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
    install_targets = {
        get_install_target_from_platform(platform)
        for platform in platforms
    }
    return {
        target: [
            platform
            for platform in platforms
            if get_install_target_from_platform(platform) == target
        ]
        for target in install_targets
    }


def is_platform_with_target_in_list(
        install_target: str,
        distinct_platforms_list: Iterable[Dict[str, Any]]
) -> bool:
    """Determines whether install target is in the list of platforms"""
    return any(
        install_target == distinct_platform['install target']
        for distinct_platform in distinct_platforms_list
    )


def get_all_platforms_for_install_target(
    install_target: str
) -> List[Dict[str, Any]]:
    """Return list of platform dictionaries for given install target."""
    platforms: List[Dict[str, Any]] = []
    all_platforms = glbl_cfg(cached=True).get(['platforms'], sparse=False)
    for k, v in all_platforms.iteritems():  # noqa: B301 (iteritems valid here)
        if (v.get('install target', k) == install_target):
            v_copy = deepcopy(v)
            v_copy['name'] = k
            platforms.append(v_copy)
    return platforms


def get_random_platform_for_install_target(
    install_target: str
) -> Dict[str, Any]:
    """Return a randomly selected platform (dict) for given install target.

    Raises:
        PlatformLookupError: We can't get a platform for this install target.
    """
    platforms = get_all_platforms_for_install_target(install_target)
    try:
        return random.choice(platforms)  # nosec (not crypto related)
    except IndexError:
        # No platforms to choose from
        raise PlatformLookupError(
            f'Could not select platform for install target: {install_target}'
        )


def get_localhost_install_target() -> str:
    """Returns the install target of localhost platform"""
    localhost = get_platform()
    return get_install_target_from_platform(localhost)


def _validate_single_host(
    platforms_cfg: Union[dict, 'OrderedDictWithDefaults']
) -> None:
    """Check that single-host platforms only specify a single host.

    Some job runners don't work across multiple hosts; the job ID is only valid
    on the specific submission host.
    """
    bad_platforms = []
    runners = set()
    name: str
    config: dict
    for name, config in platforms_cfg.items():
        runner = config.get('job runner', DEFAULT_JOB_RUNNER)
        hosts = config.get('hosts', [])
        if runner in SINGLE_HOST_JOB_RUNNERS and len(hosts) > 1:
            bad_platforms.append((name, runner, hosts))
            runners.add(runner)
    if bad_platforms:
        if len(runners) > 1:
            grammar = ["are", "s"]
        else:
            grammar = ["is a", ""]
        msg = (
            f"{', '.join(runners)} {grammar[0]} single-host"
            f" job runner{grammar[1]}:"
        )
        for name, runner, hosts in bad_platforms:
            msg += f'\n * Platform {name} ({runner}) hosts: {", ".join(hosts)}'
        raise GlobalConfigError(msg)


def validate_platforms(platforms_cfg: Dict[str, Any]) -> None:
    """Check for invalid or inconsistent platforms config."""
    _validate_single_host(platforms_cfg)

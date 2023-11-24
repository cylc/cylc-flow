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

"""Utilities for configuring logging level via the CLI."""

import logging
from typing import List, Dict, Union, TYPE_CHECKING

if TYPE_CHECKING:
    import os


def verbosity_to_log_level(verb: int) -> int:
    """Convert Cylc verbosity to log severity level."""
    if verb < 0:
        return logging.WARNING
    if verb > 0:
        return logging.DEBUG
    return logging.INFO


def log_level_to_verbosity(lvl: int) -> int:
    """Convert log severity level to Cylc verbosity.

    Examples:
        >>> log_level_to_verbosity(logging.NOTSET)
        2
        >>> log_level_to_verbosity(logging.DEBUG)
        1
        >>> log_level_to_verbosity(logging.INFO)
        0
        >>> log_level_to_verbosity(logging.WARNING)
        -1
        >>> log_level_to_verbosity(logging.ERROR)
        -1
    """
    if lvl < logging.DEBUG:
        return 2
    if lvl < logging.INFO:
        return 1
    if lvl == logging.INFO:
        return 0
    return -1


def verbosity_to_opts(verb: int) -> List[str]:
    """Convert Cylc verbosity to the CLI opts required to replicate it.

    Examples:
        >>> verbosity_to_opts(0)
        []
        >>> verbosity_to_opts(-2)
        ['-q', '-q']
        >>> verbosity_to_opts(2)
        ['-v', '-v']

    """
    return [
        '-q'
        for _ in range(verb, 0)
    ] + [
        '-v'
        for _ in range(0, verb)
    ]


def verbosity_to_env(verb: int) -> Dict[str, str]:
    """Convert Cylc verbosity to the env vars required to replicate it.

    Examples:
        >>> verbosity_to_env(0)
        {'CYLC_VERBOSE': 'false', 'CYLC_DEBUG': 'false'}
        >>> verbosity_to_env(1)
        {'CYLC_VERBOSE': 'true', 'CYLC_DEBUG': 'false'}
        >>> verbosity_to_env(2)
        {'CYLC_VERBOSE': 'true', 'CYLC_DEBUG': 'true'}

    """
    return {
        'CYLC_VERBOSE': str((verb > 0)).lower(),
        'CYLC_DEBUG': str((verb > 1)).lower(),
    }


def env_to_verbosity(env: 'Union[Dict, os._Environ]') -> int:
    """Extract verbosity from environment variables.

    Examples:
        >>> env_to_verbosity({})
        0
        >>> env_to_verbosity({'CYLC_VERBOSE': 'true'})
        1
        >>> env_to_verbosity({'CYLC_DEBUG': 'true'})
        2
        >>> env_to_verbosity({'CYLC_DEBUG': 'TRUE'})
        2

    """
    return (
        2 if env.get('CYLC_DEBUG', '').lower() == 'true'
        else 1 if env.get('CYLC_VERBOSE', '').lower() == 'true'
        else 0
    )

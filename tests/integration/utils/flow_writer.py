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
"""Utility for writing Cylc Flow configuration files.

These utilities are not intended for direct use by tests
(hence the underscore function names).
Use the fixtures provided in the conftest instead.

"""

from textwrap import dedent
from typing import List


def _write_header(name: str, level: int) -> str:
    """Write a cylc section definition."""
    indent = '    ' * (level - 1)
    return f'{indent}{"[" * level}{name}{"]" * level}'


def _write_setting(key: str, value: str, level: int) -> List[str]:
    """Write a cylc setting definition."""
    indent = '    ' * (level - 1)
    value = str(value)
    if '\n' in value:
        value = dedent(value).strip()
        ret = [f'{indent}{key} = """']
        if 'script' in key:
            ret.extend(value.splitlines())
        else:
            ret.extend([
                f'{indent}    {line}'
                for line in value.splitlines()
            ])
        ret += [f'{indent}"""']
    else:
        ret = [f'{"    " * (level - 1)}{key} = {value}']
    return ret


def _write_section(name: str, section: dict, level: int) -> List[str]:
    """Write an entire cylc section including headings and settings."""
    ret = []
    ret.append(_write_header(name, level))
    ret.extend(_write_conf(section, level))
    return ret


def _write_conf(conf: dict, level: int) -> List[str]:
    ret = []
    for key, value in conf.items():
        # write out settings first
        if key.lower() == '#!jinja2':
            ret.append('#!jinja2')
        elif not isinstance(value, dict):
            ret.extend(
                _write_setting(key, value, level + 1)
            )
    for key, value in conf.items():
        # then sections after
        if isinstance(value, dict):
            ret.extend(
                _write_section(key, value, level + 1)
            )
    return ret


def flow_config_str(conf: dict) -> str:
    """Convert a configuration dictionary into cylc/parsec format.

    Args:
        conf (dict):
            A [nested] dictionary of configurations.

    Returns:
        str - Multiline string in cylc/parsec format.

    """
    return '\n'.join(_write_conf(conf, 0)) + '\n'

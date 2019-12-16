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
# Tests for the config upgrader - this is specifically for the function
# testing that configs can be upgraded from Cylc 7 to 8.

import pytest
import os
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.cfgspec.suite import RawSuiteConfig, host_to_platform_upgrader
from cylc.flow.parsec.config import ParsecConfig

SUITERC = """
[scheduling]
[[graph]]
1 = Alice => Bob

[runtime]
[[Alice]]
platform = sugar
[[Bob]]
[[[remote]]]
    host = localhost
[[[job]]]
    batch system = slurm
"""

GLOBALRC = """
[job platforms]
[[sugar]]
remote hosts = localhost
batch system = slurm
"""


def set_up(global_rc_str, suite_rc_str, tmp_path):
    """Set up configs before and after the upgrader has been run on them,
    and return these to the test function

    Args:
        global_rc_str (str):
            String of a `global.rc` file
        suite_rc_str (str):
            String of a `suite.rc` file
        tmp_path (path object):
            A path to a temporary location to put some files.

    """
    # Set Up Config File
    globalrc = tmp_path / 'flow.rc'
    suiterc = tmp_path / 'suite.rc'
    with open(str(globalrc), 'w') as file_handle:
        file_handle.write(global_rc_str)
    with open(str(suiterc), 'w') as file_handle:
        file_handle.write(suite_rc_str)

    os.environ['CYLC_CONF_PATH'] = str(tmp_path)

    suite_config = RawSuiteConfig(str(suiterc), None, None)
    upgraded_suite_config = host_to_platform_upgrader(suite_config.sparse)
    return (suite_config, upgraded_suite_config)


@pytest.mark.parametrize(
    'task, output',
    [
        ('Alice', 'sugar'),
        ('Bob', 'sugar')
    ]
)
def test_upgrader_function(tmp_path, task, output):
    before, after = set_up(GLOBALRC, SUITERC, tmp_path)

    assert after['runtime'][task]['platform'] == output

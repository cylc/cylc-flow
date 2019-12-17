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

# A set of tasks the host_to_platform_upgrader should be able to deal with
# without hiccuping.
SUITERC = """
[runtime]
    [[alpha]]
        [[[remote]]]
            host = localhost
        [[[job]]]
            batch system = background
        # => platform = localhost (set at load time)

    [[gamma]]
        [[[job]]]
            batch system = slurm
        # => platform = sugar (set at load time)

    [[zeta]]
        [[[remote]]]
            host = hpcl1
        [[[job]]]
            batch system = background
        # => platform = hpcl1-bg (set at load time)
"""

# A set of hosts which should return a logged error message on upgrade.
BADSUITERC = """
[runtime]
    [[beta]]
        [[[remote]]]
            host = desktop01
        [[[job]]]
            batch system = slurm
        # => validation failure (no matching platform)
"""

FUNC_SUITERC = """
[runtime]
    [[delta]]
        [[[remote]]]
            host = $(rose host-select hpc)
            # assuming this returns "hpcl1" or "hpcl2"
        [[[job]]]
            batch system = pbs
        # => platform = hpc (set at job submission time)

    [[epsilon]]
        [[[remote]]]
            host = $(rose host-select hpc)
        [[[job]]]
            batch system = slurm
        # => job submission failure (no matching platform)
"""

# A global rc file (job platforms section) defining platforms which look a bit
# like those on a major Cylc user site.
GLOBALRC = """
[job platforms]
    [[desktop\d\d|laptop\d\d]]
        # hosts = platform name (default)
        # Note: "desktop01" and "desktop02" are both valid and distinct platforms
    [[sugar]]
        remote hosts = localhost
        batch system = slurm
    [[hpc]]
        remote hosts = hpcl1, hpcl2
        retrieve job logs = True
        batch system = pbs
    [[hpcl1-bg]]
        remote hosts = hpcl1
        retrieve job logs = True
        batch system = background
    [[hpcl2-bg]]
        remote hosts = hpcl2
        retrieve job logs = True
        batch system = background
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
        ('alpha', 'localhost'),
        ('gamma', 'sugar'),
        ('zeta', 'hpcl1-bg')
    ]
)
def test_upgrader_function(tmp_path, task, output):
    # Check that upgradable configs are returned with platform settings added
    # TODO ... and [task][job] / [remote] settings removed.
    if output != 'error':
        before, after = set_up(GLOBALRC, SUITERC, tmp_path)
        assert after['runtime'][task]['platform'] == output


def test_upgrader_failures(tmp_path, caplog):
    """Check that non-upgradable configs return error messages.
    """
    set_up(GLOBALRC, BADSUITERC, tmp_path)
    failed_tasks_messages = [
        f"Unable to determine platform for {name}"
        for name in ['beta']
    ]
    messages = [record.msg for record in caplog.records]
    # TODO ask MH if this is too simplistic - we could have a sort here?
    assert failed_tasks_messages==messages


def test_upgrader_where_host_is_function(tmp_path, caplog):
    """Check that where a host is given as a function the config upgrader
    returns the config unchanged, with a debug message
    The reverse lookup to be used at job-submission instead.
    """
    set_up(GLOBALRC, FUNC_SUITERC, tmp_path)
    debug_tasks_messages = [
        f"Unable to upgrade task '{name}' to platform at validation because" \
        f"the host setting contains a function. Cylc will attempt to " \
        f"upgrade this task on job submission." \
        for name in ['delta', 'epsilon']
    ]
    messages = [record.msg for record in caplog.records]
    # TODO ask MH if this is too simplistic - we could have a sort here?
    assert debug_tasks_messages==messages


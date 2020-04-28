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
# Tests for the config upgrader - this is specifically for the function
# testing that configs can be upgraded from Cylc 7 to 8.

import pytest
import os
import re
from cylc.flow.cfgspec.suite import RawSuiteConfig, host_to_platform_upgrader
from cylc.flow.exceptions import PlatformLookupError

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

    [[mu]]
        [[[remote]]]
            host = localhost

    [[zeta]]
        [[[remote]]]
            host = hpcl1
        [[[job]]]
            batch system = background
        # => platform = hpcl1-bg (set at load time)
    [[omicron]]
        [[[remote]]]
            host = hpcl1
        [[[job]]]
            batch system = background
            batch submit command template = qsub
        # => platform = hpcl1-bg (set at load time)
    [[nu]]
         platform = desktop42
"""

# A set of tasks which should return a validation failure because no
# matching platform can be found.
NOPLATFORM_SUITERC = """
[runtime]
    [[beta]]
    # => validation failure (no matching platform)
        [[[remote]]]
            host = desktop01
        [[[job]]]
            batch system = slurm
"""

# A set of tasks which should return a python error because Cylc 7 & 8
# Settings have both been used.
BADSUITERC = """
[runtime]
    [[kappa]]
        platform = sugar
        [[[remote]]]
            host = desktop01
        [[[job]]]
            batch system = slurm
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
    [[desktop[0-9]{2}|laptop[0-9]{2}]]
        # hosts = platform name (default)
        # Note: "desktop01" and "desktop02" are both valid and distinct
        # platforms
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


def memoize(func):
    cache = {}

    def memoized_func(*args):
        if args in cache:
            return cache[args]
        result = func(*args)
        cache[args] = result
        return result

    return memoized_func


@memoize
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


def test_upgrader_fn_not_used(tmp_path):
    # Check that nothing happens if nothing needs to.
    before, after = set_up(GLOBALRC, SUITERC, tmp_path)
    assert after['runtime']['nu'] == before.get(['runtime', 'nu'])


@pytest.mark.parametrize(
    'task, output',
    [
        ('alpha', 'localhost'),
        ('gamma', 'sugar'),
        ('zeta', 'hpcl1-bg'),
        ('mu', 'localhost'),
        ('omicron', 'hpcl1-bg')
    ]
)
def test_upgrader_function(tmp_path, task, output):
    # Check that upgradable configs are returned with platform settings added
    before, after = set_up(GLOBALRC, SUITERC, tmp_path)
    assert after['runtime'][task]['platform'] == output

    # Assure ourselves that the old items have been removed
    if 'remote' in after['runtime'][task].keys():
        assert 'host' not in after['runtime'][task]['remote'].keys()
    if 'job' in after['runtime'][task].keys():
        assert 'batch sytem' not in after['runtime'][task]['job'].keys()
    if 'job' in after['runtime'][task].keys():
        assert 'batch submit command template' not in \
               after['runtime'][task]['job'].keys()


def test_upgrader_fails_mixed_syntax(tmp_path):
    """Check that mixed Cylc 7/8 configs return error messages.
    """
    with pytest.raises(PlatformLookupError):
        set_up(GLOBALRC, BADSUITERC, tmp_path)


def test_upgrader_fails_noplatform(tmp_path):
    """Check that an error is raised if no matchin Platfrom is found
    """
    with pytest.raises(PlatformLookupError):
        set_up(GLOBALRC, NOPLATFORM_SUITERC, tmp_path)


def test_upgrader_where_host_is_function(tmp_path, caplog):
    """Check that where a host is given as a function the config upgrader
    returns the config unchanged, with a debug message
    The reverse lookup to be used at job-submission instead.
    """
    import logging
    caplog.set_level(logging.DEBUG)
    set_up(GLOBALRC, FUNC_SUITERC, tmp_path)
    debug_tasks_messages = [
        (f"The host setting of '{name}' is a function: "
         f"Cylc will try to upgrade this task on job submission.")
        for name in ['delta', 'epsilon']
    ]
    messages = [record.msg for record in caplog.records]
    for message in debug_tasks_messages:
        assert message in messages

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

"""
Test working of host_to_platform_upgrader function from cylc/flow/cfgspec.
This function is designed to take configs set up for Cylc 7 abd guess a
sensible platform.

Tests

- Platform Set
    - Forbidden Items set
        - fail
    - Forbidden items not set
        - nowt happens
- Platform not set
    - Host == Function
        - Log Message
    - Host !- Function
        - select correct platform
"""

import pytest
import logging

from tests.unit.conftest import mock_glbl_cfg

from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.cfgspec.suite import host_to_platform_upgrader

from tests.unit.conftest import mock_glbl_cfg


@pytest.fixture
def get_task_conf():
    CONF = {'runtime': {'sometask': {}}}
    return CONF


@pytest.mark.parametrize(
    'forbidden',
    [
        {'remote': {'host': 'alpha'}},
        {'job': {'batch system': 'loaf'}},
        {'job': {'batch submit command template': 'echo hi'}}
    ]
)
def test_platform_and_hostset__fails(forbidden, get_task_conf):
    """Try each of the 3 items which are not allowed with platforms in the
    same task config as a platform is set to ensure that all fail.
    """
    config = get_task_conf
    config['runtime']['sometask']['platform'] = 'nine_and_three_quarters'
    config['runtime']['sometask'].update(forbidden)
    with pytest.raises(PlatformLookupError, match=".*Cylc 7 .* Cylc 8.*"):
        host_to_platform_upgrader(config)


def test_platform_and_host_not_set__doesnothing(get_task_conf):
    """Assure ourselves that if a platform is given no Cylc 7 items
    the config passes through the function unaltered.
    """
    assert host_to_platform_upgrader(get_task_conf) == get_task_conf


def test_platform_and_harmless_old_items__doesnothing(get_task_conf):
    """Double check that when old items such as [job][execution time limit]
    are added to the config the config is returned unchanged.
    """
    config = get_task_conf
    config['runtime']['sometask'].update({'execution time limt': 42})
    assert host_to_platform_upgrader(get_task_conf) == \
        get_task_conf


def test_noplatform_hostfunction__logsdebug(caplog, get_task_conf):
    caplog.set_level(logging.DEBUG)
    config = get_task_conf
    config['runtime']['sometask'].update(
        {'remote': {'host': '$(echo hi)'}}
    )
    assert host_to_platform_upgrader(config) == config
    assert "'sometask' is a function" in caplog.messages[0]


def test_noplatform_hostname__selectplatform(
    get_task_conf, mock_glbl_cfg, caplog
):
    """
    Check that we can select a platform and remove forbidden items

    This test does not need to replicate the tests for the
    `platform_from_job_info` (a.k.a Reverse Lookup), just confirm
    that we are using that function correctly here.
    """
    caplog.set_level(logging.WARNING)
    mock_glbl_cfg(
        'cylc.flow.cfgspec.suite.glbl_cfg',
        '''
        [platforms]
            [[saffron]]
                remote hosts = saff01
                batch system = slurm
        '''
    )
    config = get_task_conf
    config['runtime']['sometask'].update(
        {
            'remote': {'host': 'saff01'},
            'job': {'batch system': 'slurm'}
        }
    )
    assert host_to_platform_upgrader(config) == \
        {'runtime': {'sometask': {
            'remote': {},
            'job': {},
            'platform': 'saffron'
        }}}
    assert "Cylc 8 platform \"saffron\" selected" in caplog.messages[0]


def test_noplatform_hostname__cantselectplatform(
    get_task_conf, mock_glbl_cfg
):
    """
    Check that we can select a platform and remove forbidden items

    This test does not need to replicate the tests for the
    `platform_from_job_info` (a.k.a Reverse Lookup), just confirm
    that we are using that function correctly here.
    """
    mock_glbl_cfg(
        'cylc.flow.cfgspec.suite.glbl_cfg',
        '''
        '''
    )
    config = get_task_conf
    config['runtime']['sometask'].update(
        {
            'remote': {'host': 'saff01'},
            'job': {'batch system': 'slurm'}
        }
    )
    with pytest.raises(PlatformLookupError):
        host_to_platform_upgrader(config)
